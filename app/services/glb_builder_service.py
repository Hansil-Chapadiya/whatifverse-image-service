import json
import struct


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

        # Bottom edge sits on y=0 so the model can be placed on a flat AR plane.
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

    def build_textured_plane_glb(
        self,
        image_bytes: bytes,
        image_width: int,
        image_height: int,
        image_mime_type: str = "image/png",
    ) -> bytes:
        safe_width = image_width if image_width > 0 else 1
        safe_height = image_height if image_height > 0 else safe_width
        aspect_ratio = safe_height / safe_width

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

        json_chunk = self._pad_to_4_bytes(
            json.dumps(document, separators=(",", ":"), ensure_ascii=True).encode("utf-8"),
            pad_byte=b" ",
        )
        binary_chunk = b"".join(binary_parts)

        total_length = 12 + 8 + len(json_chunk) + 8 + len(binary_chunk)
        header = struct.pack("<4sII", b"glTF", 2, total_length)
        json_header = struct.pack("<I4s", len(json_chunk), b"JSON")
        binary_header = struct.pack("<I4s", len(binary_chunk), b"BIN\x00")

        return header + json_header + json_chunk + binary_header + binary_chunk


glb_builder_service = GLBBuilderService()
