import json
import math
import struct
from dataclasses import dataclass


@dataclass
class ScenePlane:
    name: str
    image_bytes: bytes
    image_width: int
    image_height: int
    translation: tuple[float, float, float]
    scale: float = 1.0
    animate: bool = False
    float_height: float = 0.08
    pulse_scale: float = 0.04
    animation_phase: float = 0.0
    image_mime_type: str = "image/png"


class GLBBuilderService:
    @staticmethod
    def _pad_to_4_bytes(data: bytes, pad_byte: bytes = b"\x00") -> bytes:
        padding = (-len(data)) % 4
        if padding == 0:
            return data
        return data + (pad_byte * padding)

    @staticmethod
    def _build_plane_buffers(aspect_ratio: float) -> tuple[bytes, bytes, bytes]:
        plane_width = 1.0
        plane_height = max(aspect_ratio, 0.25)
        half_width = plane_width / 2.0

        positions = [
            -half_width,
            0.0,
            0.0,
            half_width,
            0.0,
            0.0,
            half_width,
            plane_height,
            0.0,
            -half_width,
            plane_height,
            0.0,
        ]
        texcoords = [
            0.0,
            1.0,
            1.0,
            1.0,
            1.0,
            0.0,
            0.0,
            0.0,
        ]
        indices = [0, 1, 2, 0, 2, 3]

        position_bytes = struct.pack("<12f", *positions)
        texcoord_bytes = struct.pack("<8f", *texcoords)
        index_bytes = struct.pack("<6H", *indices)
        return position_bytes, texcoord_bytes, index_bytes

    @staticmethod
    def _build_unit_plane_buffers() -> tuple[bytes, bytes, bytes]:
        positions = [
            -0.5,
            0.0,
            0.0,
            0.5,
            0.0,
            0.0,
            0.5,
            1.0,
            0.0,
            -0.5,
            1.0,
            0.0,
        ]
        texcoords = [
            0.0,
            1.0,
            1.0,
            1.0,
            1.0,
            0.0,
            0.0,
            0.0,
        ]
        indices = [0, 1, 2, 0, 2, 3]
        return (
            struct.pack("<12f", *positions),
            struct.pack("<8f", *texcoords),
            struct.pack("<6H", *indices),
        )

    @staticmethod
    def _resolve_aspect_ratio(image_width: int, image_height: int) -> float:
        safe_width = image_width if image_width > 0 else 1
        safe_height = image_height if image_height > 0 else safe_width
        return max(safe_height / safe_width, 0.25)

    @staticmethod
    def _build_animation_times() -> tuple[list[float], bytes]:
        times = [0.0, 1.25, 2.5, 3.75]
        return times, struct.pack("<4f", *times)

    @staticmethod
    def _build_translation_samples(plane: ScenePlane, times: list[float]) -> bytes:
        samples: list[float] = []
        duration = times[-1] if times and times[-1] > 0 else 1.0
        base_x, base_y, base_z = plane.translation
        phase = plane.animation_phase % 1.0
        for time_value in times:
            wave = math.sin((((time_value / duration) + phase) * math.tau))
            samples.extend([base_x, base_y + (wave * plane.float_height), base_z])
        return struct.pack(f"<{len(samples)}f", *samples)

    @staticmethod
    def _build_scale_samples(plane_scale: list[float], plane: ScenePlane, times: list[float]) -> bytes:
        samples: list[float] = []
        duration = times[-1] if times and times[-1] > 0 else 1.0
        phase = plane.animation_phase % 1.0
        base_x, base_y, base_z = plane_scale
        for time_value in times:
            wave = math.sin((((time_value / duration) + phase) * math.tau))
            scale_multiplier = 1.0 + (wave * plane.pulse_scale)
            samples.extend([base_x * scale_multiplier, base_y * scale_multiplier, base_z])
        return struct.pack(f"<{len(samples)}f", *samples)

    def _finalize_glb(self, document: dict, binary_parts: list[bytes]) -> bytes:
        binary_chunk = b"".join(binary_parts)
        document["buffers"] = [{"byteLength": len(binary_chunk)}]
        if document.get("animations") == []:
            document.pop("animations", None)

        json_chunk = self._pad_to_4_bytes(
            json.dumps(document, separators=(",", ":"), ensure_ascii=True).encode("utf-8"),
            pad_byte=b" ",
        )

        total_length = 12 + 8 + len(json_chunk) + 8 + len(binary_chunk)
        header = struct.pack("<4sII", b"glTF", 2, total_length)
        json_header = struct.pack("<I4s", len(json_chunk), b"JSON")
        binary_header = struct.pack("<I4s", len(binary_chunk), b"BIN\x00")
        return header + json_header + json_chunk + binary_header + binary_chunk

    def build_textured_plane_glb(
        self,
        image_bytes: bytes,
        image_width: int,
        image_height: int,
        image_mime_type: str = "image/png",
    ) -> bytes:
        aspect_ratio = self._resolve_aspect_ratio(image_width, image_height)
        position_bytes, texcoord_bytes, index_bytes = self._build_plane_buffers(aspect_ratio)

        binary_parts: list[bytes] = []
        current_offset = 0

        def add_binary_part(data: bytes) -> tuple[int, int]:
            nonlocal current_offset
            padded = self._pad_to_4_bytes(data)
            start_offset = current_offset
            binary_parts.append(padded)
            current_offset += len(padded)
            return start_offset, len(data)

        position_offset, position_length = add_binary_part(position_bytes)
        texcoord_offset, texcoord_length = add_binary_part(texcoord_bytes)
        index_offset, index_length = add_binary_part(index_bytes)
        image_offset, image_length = add_binary_part(image_bytes)

        plane_height = max(aspect_ratio, 0.25)
        document = {
            "asset": {"version": "2.0", "generator": "whatifverse-image-service-v2"},
            "scene": 0,
            "scenes": [{"nodes": [0]}],
            "nodes": [{"mesh": 0, "name": "root-plane"}],
            "meshes": [
                {
                    "name": "textured-plane",
                    "primitives": [
                        {
                            "attributes": {"POSITION": 0, "TEXCOORD_0": 1},
                            "indices": 2,
                            "material": 0,
                        }
                    ],
                }
            ],
            "materials": [
                {
                    "name": "plane-material",
                    "doubleSided": True,
                    "alphaMode": "BLEND",
                    "pbrMetallicRoughness": {
                        "baseColorTexture": {"index": 0},
                        "metallicFactor": 0.0,
                        "roughnessFactor": 1.0,
                    },
                }
            ],
            "textures": [{"sampler": 0, "source": 0}],
            "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497}],
            "images": [{"bufferView": 3, "mimeType": image_mime_type, "name": "embedded-preview"}],
            "buffers": [{"byteLength": current_offset}],
            "bufferViews": [
                {"buffer": 0, "byteOffset": position_offset, "byteLength": position_length, "target": 34962},
                {"buffer": 0, "byteOffset": texcoord_offset, "byteLength": texcoord_length, "target": 34962},
                {"buffer": 0, "byteOffset": index_offset, "byteLength": index_length, "target": 34963},
                {"buffer": 0, "byteOffset": image_offset, "byteLength": image_length},
            ],
            "accessors": [
                {
                    "bufferView": 0,
                    "componentType": 5126,
                    "count": 4,
                    "type": "VEC3",
                    "min": [-0.5, 0.0, 0.0],
                    "max": [0.5, plane_height, 0.0],
                },
                {
                    "bufferView": 1,
                    "componentType": 5126,
                    "count": 4,
                    "type": "VEC2",
                    "min": [0.0, 0.0],
                    "max": [1.0, 1.0],
                },
                {
                    "bufferView": 2,
                    "componentType": 5123,
                    "count": 6,
                    "type": "SCALAR",
                    "min": [0],
                    "max": [3],
                },
            ],
        }

        return self._finalize_glb(document, binary_parts)

    def build_animated_scene_glb(self, planes: list[ScenePlane]) -> bytes:
        if not planes:
            raise ValueError("Animated scene GLB requires at least one plane")

        binary_parts: list[bytes] = []
        current_offset = 0

        def add_binary_part(data: bytes) -> tuple[int, int]:
            nonlocal current_offset
            padded = self._pad_to_4_bytes(data)
            start_offset = current_offset
            binary_parts.append(padded)
            current_offset += len(padded)
            return start_offset, len(data)

        position_bytes, texcoord_bytes, index_bytes = self._build_unit_plane_buffers()
        animation_times, animation_times_bytes = self._build_animation_times()

        position_offset, position_length = add_binary_part(position_bytes)
        texcoord_offset, texcoord_length = add_binary_part(texcoord_bytes)
        index_offset, index_length = add_binary_part(index_bytes)
        time_offset, time_length = add_binary_part(animation_times_bytes)

        document = {
            "asset": {"version": "2.0", "generator": "whatifverse-image-service-v2-animated-scene"},
            "scene": 0,
            "scenes": [{"nodes": [0]}],
            "nodes": [{"name": "scenario-root", "children": []}],
            "meshes": [],
            "materials": [],
            "textures": [],
            "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497}],
            "images": [],
            "buffers": [{"byteLength": 0}],
            "bufferViews": [
                {"buffer": 0, "byteOffset": position_offset, "byteLength": position_length, "target": 34962},
                {"buffer": 0, "byteOffset": texcoord_offset, "byteLength": texcoord_length, "target": 34962},
                {"buffer": 0, "byteOffset": index_offset, "byteLength": index_length, "target": 34963},
                {"buffer": 0, "byteOffset": time_offset, "byteLength": time_length},
            ],
            "accessors": [
                {
                    "bufferView": 0,
                    "componentType": 5126,
                    "count": 4,
                    "type": "VEC3",
                    "min": [-0.5, 0.0, 0.0],
                    "max": [0.5, 1.0, 0.0],
                },
                {
                    "bufferView": 1,
                    "componentType": 5126,
                    "count": 4,
                    "type": "VEC2",
                    "min": [0.0, 0.0],
                    "max": [1.0, 1.0],
                },
                {
                    "bufferView": 2,
                    "componentType": 5123,
                    "count": 6,
                    "type": "SCALAR",
                    "min": [0],
                    "max": [3],
                },
                {
                    "bufferView": 3,
                    "componentType": 5126,
                    "count": len(animation_times),
                    "type": "SCALAR",
                    "min": [min(animation_times)],
                    "max": [max(animation_times)],
                },
            ],
            "animations": [{"name": "idle-scene-animation", "samplers": [], "channels": []}],
        }

        animation_time_accessor_index = 3
        animation_section = document["animations"][0]

        for index, plane in enumerate(planes):
            aspect_ratio = self._resolve_aspect_ratio(plane.image_width, plane.image_height)
            node_scale = [plane.scale, plane.scale * aspect_ratio, 1.0]

            image_offset, image_length = add_binary_part(plane.image_bytes)
            image_buffer_view_index = len(document["bufferViews"])
            document["bufferViews"].append(
                {"buffer": 0, "byteOffset": image_offset, "byteLength": image_length}
            )

            image_index = len(document["images"])
            texture_index = len(document["textures"])
            material_index = len(document["materials"])
            mesh_index = len(document["meshes"])
            node_index = len(document["nodes"])

            document["images"].append(
                {
                    "bufferView": image_buffer_view_index,
                    "mimeType": plane.image_mime_type,
                    "name": f"{plane.name}-image",
                }
            )
            document["textures"].append({"sampler": 0, "source": image_index})
            document["materials"].append(
                {
                    "name": f"{plane.name}-material",
                    "doubleSided": True,
                    "alphaMode": "BLEND",
                    "pbrMetallicRoughness": {
                        "baseColorTexture": {"index": texture_index},
                        "metallicFactor": 0.0,
                        "roughnessFactor": 1.0,
                    },
                }
            )
            document["meshes"].append(
                {
                    "name": f"{plane.name}-mesh",
                    "primitives": [
                        {
                            "attributes": {"POSITION": 0, "TEXCOORD_0": 1},
                            "indices": 2,
                            "material": material_index,
                        }
                    ],
                }
            )
            document["nodes"].append(
                {
                    "name": plane.name,
                    "mesh": mesh_index,
                    "translation": list(plane.translation),
                    "scale": node_scale,
                }
            )
            document["nodes"][0]["children"].append(node_index)

            if plane.animate:
                translation_bytes = self._build_translation_samples(plane, animation_times)
                scale_bytes = self._build_scale_samples(node_scale, plane, animation_times)

                translation_offset, translation_length = add_binary_part(translation_bytes)
                translation_buffer_view_index = len(document["bufferViews"])
                document["bufferViews"].append(
                    {"buffer": 0, "byteOffset": translation_offset, "byteLength": translation_length}
                )
                translation_accessor_index = len(document["accessors"])
                document["accessors"].append(
                    {
                        "bufferView": translation_buffer_view_index,
                        "componentType": 5126,
                        "count": len(animation_times),
                        "type": "VEC3",
                    }
                )

                scale_offset, scale_length = add_binary_part(scale_bytes)
                scale_buffer_view_index = len(document["bufferViews"])
                document["bufferViews"].append(
                    {"buffer": 0, "byteOffset": scale_offset, "byteLength": scale_length}
                )
                scale_accessor_index = len(document["accessors"])
                document["accessors"].append(
                    {
                        "bufferView": scale_buffer_view_index,
                        "componentType": 5126,
                        "count": len(animation_times),
                        "type": "VEC3",
                    }
                )

                translation_sampler_index = len(animation_section["samplers"])
                animation_section["samplers"].append(
                    {
                        "input": animation_time_accessor_index,
                        "output": translation_accessor_index,
                        "interpolation": "LINEAR",
                    }
                )
                animation_section["channels"].append(
                    {
                        "sampler": translation_sampler_index,
                        "target": {"node": node_index, "path": "translation"},
                    }
                )

                scale_sampler_index = len(animation_section["samplers"])
                animation_section["samplers"].append(
                    {
                        "input": animation_time_accessor_index,
                        "output": scale_accessor_index,
                        "interpolation": "LINEAR",
                    }
                )
                animation_section["channels"].append(
                    {
                        "sampler": scale_sampler_index,
                        "target": {"node": node_index, "path": "scale"},
                    }
                )

        return self._finalize_glb(document, binary_parts)


glb_builder_service = GLBBuilderService()
