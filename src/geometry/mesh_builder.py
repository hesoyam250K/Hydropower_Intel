"""Procedural 3D mesh generator for hydropower installations and hydrothermal bridges.

Generates realistic, mathematically proportioned engineering solids using Trimesh.
Provides components for:
1. Hydropower Scheme: Reservoir, Dam/Intake, Gate, Penstock, Powerhouse, Turbine, Generator, Tailrace.
2. Hydrothermal Bridge: Deck, Conduit, Fluid Core, Supporting Piers, Expansion Joints, Thermal Saddles.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
import trimesh
from trimesh.creation import box, cylinder


@dataclass
class Component3D:
    """An individual engineering component mesh in the 3D scene."""
    component_id: str
    name: str
    category: str  # 'hydropower' or 'bridge'
    mesh: trimesh.Trimesh
    base_color_rgba: Tuple[int, int, int, int]
    description: str
    metadata: Dict[str, str] = field(default_factory=dict)


class PlantGeometryBuilder:
    """Builds the coupled Hydropower and Hydrothermal Bridge 3D assembly."""

    def __init__(
        self,
        gross_head_m: float = 25.0,
        pipe_diameter_m: float = 0.50,
        bridge_length_m: float = 60.0,
        conduit_diameter_m: float = 0.40,
        include_bridge: bool = True
    ):
        self.gross_head = float(gross_head_m)
        self.penstock_d = float(pipe_diameter_m)
        self.bridge_l = float(bridge_length_m)
        self.conduit_d = float(conduit_diameter_m)
        self.include_bridge = include_bridge

    def build_all_components(self) -> Dict[str, Component3D]:
        """Constructs all 3D solid elements with realistic civil/mechanical proportions."""
        components: Dict[str, Component3D] = {}

        # Scale coordinates based on head and length
        h = max(10.0, min(80.0, self.gross_head))
        scale_z = h / 25.0
        p_diam = max(0.6, self.penstock_d * 1.5)  # Visual scaling for clear visibility

        # =========================================================================
        # 1. HYDROPOWER INSTALLATION
        # =========================================================================

        # 1.1 Upstream Reservoir Water Body
        res_mesh = box(extents=[35.0, 30.0, 18.0 * scale_z])
        res_mesh.apply_translation([-17.5, 0.0, 9.0 * scale_z])
        components["reservoir_water"] = Component3D(
            component_id="reservoir_water",
            name="Upstream Reservoir Water Body",
            category="hydropower",
            mesh=res_mesh,
            base_color_rgba=(30, 144, 255, 180),  # Deep hydraulic blue with transparency
            description="Forebay storage maintaining upstream static hydraulic head elevation.",
            metadata={"domain": "Fluid (Water)", "typical_temp": "4°C - 16°C"}
        )

        # 1.2 Concrete Gravity Dam & Intake Crest
        dam_mesh = box(extents=[12.0, 36.0, 22.0 * scale_z])
        dam_mesh.apply_translation([6.0, 0.0, 11.0 * scale_z])
        components["dam_structure"] = Component3D(
            component_id="dam_structure",
            name="Concrete Gravity Dam & Intake Weir",
            category="hydropower",
            mesh=dam_mesh,
            base_color_rgba=(140, 150, 160, 255),  # Concrete grey
            description="Mass concrete retaining barrier and penstock intake bellmouth entrance.",
            metadata={"material": "Reinforced Concrete C30/37", "structural_role": "Hydraulic Head Retention"}
        )

        # 1.3 Intake Control Sluice Gate
        gate_mesh = box(extents=[3.0, 6.0, 8.0 * scale_z])
        gate_mesh.apply_translation([12.0, 0.0, 18.0 * scale_z])
        components["intake_gate"] = Component3D(
            component_id="intake_gate",
            name="Intake Control Sluice Gate",
            category="hydropower",
            mesh=gate_mesh,
            base_color_rgba=(220, 38, 38, 255),  # Safety red
            description="Motorized head gate regulating intake penstock flow admission.",
            metadata={"actuation": "Hydraulic Cylinder", "status": "Operable"}
        )

        # 1.4 Inclined Penstock Pipe
        penstock_len = 45.0
        penstock_mesh = cylinder(radius=p_diam, height=penstock_len, sections=24)
        # Rotate to slope down from dam crest to powerhouse
        angle_rad = -np.arctan2(18.0 * scale_z, 38.0)
        rot_matrix = trimesh.transformations.rotation_matrix(angle_rad, [0, 1, 0])
        penstock_mesh.apply_transform(rot_matrix)
        penstock_mesh.apply_translation([31.0, 0.0, 10.0 * scale_z])
        components["penstock_pipe"] = Component3D(
            component_id="penstock_pipe",
            name="High-Pressure Steel Penstock",
            category="hydropower",
            mesh=penstock_mesh,
            base_color_rgba=(71, 85, 105, 255),  # Dark steel
            description="High-pressure conduit conveying water from intake to turbine casing.",
            metadata={"material": "Welded Structural Steel S355", "pressure_class": "PN25"}
        )

        # 1.5 Powerhouse Building
        house_mesh = box(extents=[16.0, 18.0, 12.0])
        house_mesh.apply_translation([56.0, 0.0, 6.0])
        components["powerhouse_casing"] = Component3D(
            component_id="powerhouse_casing",
            name="Powerhouse Substructure & Hall",
            category="hydropower",
            mesh=house_mesh,
            base_color_rgba=(100, 116, 139, 230),  # Industrial charcoal
            description="Reinforced concrete hall housing hydraulic turbine, generator, and switchgear.",
            metadata={"enclosure": "Acoustic / Weather Barrier", "foundation": "Bedrock Anchored"}
        )

        # 1.6 Turbine Runner / Spiral Scroll Casing
        turb_mesh = cylinder(radius=3.5, height=3.0, sections=24)
        turb_mesh.apply_translation([54.0, 0.0, 2.0])
        components["turbine_runner"] = Component3D(
            component_id="turbine_runner",
            name="Turbine Runner & Spiral Casing",
            category="hydropower",
            mesh=turb_mesh,
            base_color_rgba=(245, 158, 11, 255),  # Amber gold
            description="Reaction/Impulse runner converting fluid pressure and momentum into shaft torque.",
            metadata={"runner_family": "Francis / Pelton", "coupling": "Vertical / Horizontal Shaft"}
        )

        # 1.7 Synchronous Generator
        gen_mesh = cylinder(radius=2.8, height=4.5, sections=24)
        gen_mesh.apply_translation([54.0, 0.0, 6.5])
        components["generator_stator"] = Component3D(
            component_id="generator_stator",
            name="Synchronous 3-Phase AC Generator",
            category="hydropower",
            mesh=gen_mesh,
            base_color_rgba=(16, 185, 129, 255),  # Generator emerald green
            description="Direct-coupled synchronous electromagnetic generator with brushless exciter.",
            metadata={"output_voltage": "400 V / 6.6 kV", "frequency": "50.0 Hz Synchronous"}
        )

        # 1.8 Downstream Tailrace Discharge Channel
        tail_mesh = box(extents=[35.0, 14.0, 4.0])
        tail_mesh.apply_translation([78.0, 0.0, 1.5])
        components["draft_tube_tailrace"] = Component3D(
            component_id="draft_tube_tailrace",
            name="Draft Tube & Tailrace Channel",
            category="hydropower",
            mesh=tail_mesh,
            base_color_rgba=(56, 189, 248, 180),  # Tailwater blue
            description="Velocity-head recovery draft tube returning discharged water to river.",
            metadata={"discharge_type": "Submerged Free Discharge", "suction_head": "Recovered"}
        )

        # =========================================================================
        # 2. HYDROTHERMAL BRIDGE & CONDUIT (Integrated Crossing Assembly)
        # =========================================================================
        if self.include_bridge:
            bridge_y = -18.0  # Parallel crossing span
            span = max(40.0, min(120.0, self.bridge_l))

            # 2.1 Bridge Deck & Box Girder
            deck_mesh = box(extents=[span, 7.0, 2.2])
            deck_mesh.apply_translation([30.0, bridge_y, 14.0])
            components["bridge_deck"] = Component3D(
                component_id="bridge_deck",
                name="Hydrothermal Aqueduct / Bridge Deck",
                category="bridge",
                mesh=deck_mesh,
                base_color_rgba=(160, 170, 185, 255),  # Concrete deck
                description="Prestressed concrete box girder carrying vehicular access and hydrothermal conduits.",
                metadata={"span_length": f"{span:.1f} m", "material": "Prestressed Concrete C40/50"}
            )

            # 2.2 Fluid-Carrying Conduit Pipe
            conduit_mesh = cylinder(radius=self.conduit_d, height=span - 2.0, sections=20)
            # Lay cylinder along X-axis
            rot_x = trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0])
            conduit_mesh.apply_transform(rot_x)
            conduit_mesh.apply_translation([30.0, bridge_y + 1.8, 15.0])
            components["conduit_pipe"] = Component3D(
                component_id="conduit_pipe",
                name="Hydrothermal Fluid Conduit",
                category="bridge",
                mesh=conduit_mesh,
                base_color_rgba=(239, 68, 68, 255),  # Thermal red/orange pipe
                description="Insulated or bare structural conduit conveying geothermal / hydrothermal discharge.",
                metadata={"internal_diameter": f"{self.conduit_d*1000:.0f} mm", "service": "Hydrothermal Fluid"}
            )

            # 2.3 Bridge Supporting Piers
            pier1 = cylinder(radius=1.8, height=13.0, sections=18)
            pier1.apply_translation([10.0, bridge_y, 6.5])
            pier2 = cylinder(radius=1.8, height=13.0, sections=18)
            pier2.apply_translation([50.0, bridge_y, 6.5])
            piers_combined = trimesh.util.concatenate([pier1, pier2])
            components["bridge_piers"] = Component3D(
                component_id="bridge_piers",
                name="Bridge Substructure Piers & Abutments",
                category="bridge",
                mesh=piers_combined,
                base_color_rgba=(100, 110, 125, 255),  # Pier grey
                description="Reinforced concrete piers transmitting bridge dead/live loads to gorge foundation.",
                metadata={"foundation": "Rock Socketed Caissons", "restraint": "Guided Bearings"}
            )

            # 2.4 Thermal Bridge Contact Saddles (Thermal Plume / Heat Leak Zones)
            saddle1 = box(extents=[2.5, 4.0, 1.0])
            saddle1.apply_translation([10.0, bridge_y, 13.0])
            saddle2 = box(extents=[2.5, 4.0, 1.0])
            saddle2.apply_translation([50.0, bridge_y, 13.0])
            saddles = trimesh.util.concatenate([saddle1, saddle2])
            components["thermal_bridge_regions"] = Component3D(
                component_id="thermal_bridge_regions",
                name="Structural Thermal Bridge Contact Saddles",
                category="bridge",
                mesh=saddles,
                base_color_rgba=(249, 115, 22, 255),  # Thermal hotspot orange
                description="Uninsulated structural bearing interfaces where conductive heat escapes into piers.",
                metadata={"phenomenon": "Thermal Bridge (High Linear Transmittance)", "psi": "0.35 W/m·K"}
            )

            # 2.5 Expansion Joints
            joint1 = box(extents=[0.6, 7.5, 2.4])
            joint1.apply_translation([10.0, bridge_y, 14.0])
            joint2 = box(extents=[0.6, 7.5, 2.4])
            joint2.apply_translation([50.0, bridge_y, 14.0])
            joints = trimesh.util.concatenate([joint1, joint2])
            components["expansion_joints"] = Component3D(
                component_id="expansion_joints",
                name="Elastomeric Expansion Joints",
                category="bridge",
                mesh=joints,
                base_color_rgba=(234, 179, 8, 255),  # Yellow joint seal
                description="Movement joints accommodating cyclic seasonal thermal expansion and contraction.",
                metadata={"movement_capacity": "± 50 mm", "type": "Finger / Modular Elastomeric"}
            )

        return components
