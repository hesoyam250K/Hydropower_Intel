"""CAD/BIM and Engineering Software Interoperability package for HydroPower Intelligence.

Supports:
- IFC 4.3 (Bridges, dams, civil structures)
- LandXML (Topography, surfaces, alignments, pipe networks)
- STEP / IGES (Turbine and mechanical CAD geometry)
- STL / OBJ (General solid engineering geometry)
- GLB / GLTF (Viewer-ready 3D models with scene hierarchy)
- GeoJSON / GIS (Geographic coordinates, site boundaries)
- Autodesk Platform Services (APS) & Bentley iTwin cloud connectors
- HEC-RAS hydraulic simulation model ingest
"""

from src.cad.importer import CADImporter, ImportedModelResult
from src.cad.connectors import AutodeskAPSConnector, BentleyITwinConnector, HECRASConnector
from src.cad.sensor_mesh_mapper import SensorMeshMapper

__all__ = [
    "CADImporter",
    "ImportedModelResult",
    "AutodeskAPSConnector",
    "BentleyITwinConnector",
    "HECRASConnector",
    "SensorMeshMapper",
]
