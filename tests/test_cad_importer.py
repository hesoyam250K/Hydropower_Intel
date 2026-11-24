"""Unit tests for CAD, BIM, and Engineering Interoperability Engine."""

import io
import json
import pytest
import trimesh

from src.cad.importer import CADImporter, ImportedModelResult
from src.cad.connectors import AutodeskAPSConnector, BentleyITwinConnector, HECRASConnector
from src.cad.sensor_mesh_mapper import SensorMeshMapper


@pytest.fixture
def importer(tmp_path):
    return CADImporter(output_dir=str(tmp_path / "models"))


def test_import_stl(importer):
    """Verifies importing 3D STL solid geometry."""
    # Create simple box mesh and export as STL
    box = trimesh.creation.box(extents=[10, 10, 10])
    stl_bytes = box.export(file_type="stl")

    res = importer.import_file(stl_bytes, "penstock_support.stl")
    assert res.success is True
    assert res.format_type == "STL"
    assert res.total_vertices > 0
    assert res.total_faces > 0
    assert len(res.components) == 1
    assert res.glb_bytes is not None


def test_import_obj(importer):
    """Verifies Wavefront OBJ geometry parsing with named subcomponents."""
    obj_content = """# Wavefront OBJ sample
o Turbine_Rotor
v 0.0 0.0 0.0
v 1.0 0.0 0.0
v 0.0 1.0 0.0
f 1 2 3
o Casing_Cover
v 2.0 0.0 0.0
v 3.0 0.0 0.0
v 2.0 1.0 0.0
f 4 5 6
"""
    res = importer.import_file(obj_content.encode("utf-8"), "francis_turbine.obj")
    assert res.success is True
    assert res.format_type == "OBJ"
    assert res.total_faces == 2
    assert len(res.components) == 2
    assert any("Turbine_Rotor" in c["name"] for c in res.components)


def test_import_landxml(importer):
    """Verifies LandXML TIN surface and pipe network parsing."""
    landxml_content = """<?xml version="1.0"?>
<LandXML version="1.2">
  <Surfaces>
    <Surface name="Dam_Basin_Topography">
      <Definition>
        <Pnts>
          <P id="1">4000000.0 500000.0 120.0</P>
          <P id="2">4000050.0 500000.0 125.0</P>
          <P id="3">4000025.0 500040.0 118.0</P>
        </Pnts>
        <Faces>
          <F>1 2 3</F>
        </Faces>
      </Definition>
    </Surface>
  </Surfaces>
  <PipeNetworks>
    <PipeNetwork name="Hydropower_Penstocks">
      <Pipe name="Penstock_01" diameter="0.80"/>
    </PipeNetwork>
  </PipeNetworks>
</LandXML>
"""
    res = importer.import_file(landxml_content.encode("utf-8"), "dam_site.xml")
    assert res.success is True
    assert res.format_type == "LANDXML"
    assert len(res.components) >= 2
    # Verify coordinate normalization occurred for 4,000,000 coordinate
    assert res.geographic_origin.get("shifted_to_local_origin") is True


def test_import_ifc_step(importer):
    """Verifies IFC 4.3 STEP header, entity and GlobalId extraction."""
    ifc_content = """ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('ViewDefinition [CoordinationView]'),'2;1');
FILE_NAME('Bridge_Pier.ifc','2026-11-24T12:00:00',('CivilEngineer'),('HydropowerCorp'),'','','');
FILE_SCHEMA(('IFC4X3'));
ENDSEC;
DATA;
#1=IFCCARTESIANPOINT((0.0,0.0,0.0));
#2=IFCCARTESIANPOINT((5.0,0.0,0.0));
#3=IFCCARTESIANPOINT((2.5,4.0,0.0));
#4=IFCPOLYLOOP((#1,#2,#3));
#5=IFCBRIDGE('2B3$xW12H98f7e2kLmNOPQ',#10,'HydroBridge_Pier_01',$,$,$,$,$,.PIER.);
#6=IFCWALL('1A2$xW12H98f7e2kLmNOPR',#10,'Concrete_Dam_Wall',$,$,$,$,$,.SOLIDWALL.);
ENDSEC;
END-ISO-10303-21;
"""
    res = importer.import_file(ifc_content.encode("utf-8"), "bridge_pier.ifc")
    assert res.success is True
    assert res.format_type == "IFC"
    assert len(res.components) >= 1
    assert any("2B3$xW12H98f7e2kLmNOPQ" in c.get("global_id", "") or "HydroBridge" in c.get("name", "") for c in res.components)


def test_import_geojson(importer):
    """Verifies GeoJSON site boundary extrusion to 3D civil footprint."""
    geojson_data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "Powerhouse_Footprint", "type": "Substructure"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [-121.50, 44.50],
                        [-121.5005, 44.50],
                        [-121.5005, 44.5005],
                        [-121.50, 44.5005],
                        [-121.50, 44.50]
                    ]]
                }
            }
        ]
    }
    res = importer.import_file(json.dumps(geojson_data).encode("utf-8"), "site_boundary.geojson")
    assert res.success is True
    assert res.format_type == "GEOJSON"
    assert len(res.components) == 1
    assert res.total_vertices > 0


def test_empty_file_handling(importer):
    """Verifies graceful handling of empty or invalid files."""
    res = importer.import_file(b"", "empty_model.stl")
    assert res.success is False
    assert "empty" in res.errors[0].lower()

    res_unsupp = importer.import_file(b"data", "test.unknown")
    assert res_unsupp.success is False
    assert "unsupported" in res_unsupp.errors[0].lower()


def test_cloud_connectors_offline_mode():
    """Verifies Autodesk and Bentley connectors behave safely and predictably offline."""
    aps = AutodeskAPSConnector(client_id="", client_secret="")
    status = aps.check_status()
    assert status.is_offline is True
    conv = aps.convert_cad_cloud_model("test.rvt")
    assert conv["success"] is False
    assert "credentials" in conv["error"].lower()

    itwin = BentleyITwinConnector(client_id="", client_secret="")
    status_itwin = itwin.check_status()
    assert status_itwin.is_offline is True


def test_hecras_report_parsing():
    """Verifies HEC-RAS hydraulic output text parsing."""
    sample_rep = """
    HEC-RAS Plan: 100-Year Peak Flood Inflow
    Geom: Clearwater Dam and Spillway
    Cross Section 1024.5
    W.S. Elev: 108.45 m
    Vel Chnl: 3.42 m/s
    Spillway Gate 02 Hydrostatic: 425.8 kPa
    """
    hec = HECRASConnector()
    parsed = hec.parse_report_file(sample_rep)
    assert parsed["success"] is True
    assert parsed["extracted_sensors"]["HECRAS_GATE02_PRESS"] == 425.8
    assert parsed["mean_channel_velocity_mps"] == 3.42


def test_sensor_mesh_mapper():
    """Verifies sensor-to-mesh lookup."""
    mapper = SensorMeshMapper()
    comp = mapper.get_component_id("SCADA_TURB1_VIB_X")
    assert comp == "turbine_runner"

    # Resolving mesh name
    available = ["dam_structure", "Turbine_01_MainShaft", "penstock_pipe"]
    resolved = mapper.resolve_mesh_name("SCADA_TURB1_VIB_X", available)
    assert resolved == "Turbine_01_MainShaft"
