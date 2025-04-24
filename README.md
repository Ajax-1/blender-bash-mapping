# Blender Multi-Camera Texture Mapper

A Python script for applying multiple textures to a 3D model from different camera viewpoints in Blender. Perfect for creating models with different texture perspectives for games, VR/AR applications, and 3D visualization.

## Features

- 📸 Support for multiple camera perspectives
- 🎨 Apply different textures from each camera viewpoint
- 🧩 Automatically select faces based on their position and normal direction
- 🔄 Precise UV projection from camera view
- 📝 Detailed logging for debugging
- ⚙️ Flexible JSON configuration
- 📦 Export to GLB format
- 🔄 **NEW**: Batch processing mode for handling multiple files

## Requirements

- Blender 3.0+ (tested on Blender 4.4)
- Python 3.8+

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/blender-multi-camera-texture-mapper.git
cd blender-multi-camera-texture-mapper
```

2. No additional Python packages are required as the script uses Blender's built-in modules.

## Usage

### Single File Mode

```bash
blender --background --python blender_mapper.py -- --single --input input.ply --config config.json --output output.glb
```

Or use the traditional positional arguments (for backward compatibility):

```bash
blender --background --python blender_mapper.py -- input.ply config.json output.glb
```

### Batch Processing Mode

```bash
blender --background --python blender_mapper.py -- --batch --input-dir /path/to/ply/files --config config.json --output-dir /path/to/output/folder
```

### Advanced Options

```bash
blender --background --python blender_mapper.py -- --batch --input-dir ./models --config config.json --output-dir ./output --verbose --log processing.log
```

### Parameters

#### Single File Mode
- `--single`: Enable single file mode (default)
- `--input`: Path to the input 3D model in PLY format
- `--config`: Path to the camera configuration file
- `--output`: Path for the output GLB file

#### Batch Processing Mode
- `--batch`: Enable batch processing mode
- `--input-dir`: Directory containing input PLY files
- `--output-dir`: Directory for output GLB files
- `--config`: Path to the camera configuration file (shared for all models)

#### Common Options
- `--verbose`: Enable detailed logging
- `--log`: Specify a log file path

## Configuration File Format

The configuration file is a JSON array where each object represents a camera setup:

```json
[
  {
    "name": "Camera_Top",
    "location": [0, 0, 16],
    "rotation": [0, 0, 1.5708],
    "selection_params": {
      "type": "max_coord",
      "coord": 2,
      "epsilon": 1.5,
      "normal_direction": 1
    },
    "material_index": 0,
    "texture_path": "/path/to/texture_top.png"
  },
  {
    "name": "Camera_Side",
    "location": [14, 0, 1.3],
    "rotation": [1.5708, 0, 1.5708],
    "selection_params": {
      "type": "max_coord",
      "coord": 0,
      "epsilon": 1.5,
      "normal_direction": 1
    },
    "material_index": 1,
    "texture_path": "/path/to/texture_side.png"
  }
]
```

### Configuration Parameters

#### Camera Settings
- `name`: Camera identifier
- `location`: [x, y, z] camera position
- `rotation`: [x, y, z] rotation in radians
- `material_index`: Index of the material to assign (starting from 0)
- `texture_path`: Path to texture image file

#### Face Selection Parameters
- `type`: Selection method (currently supported: "max_coord", "min_coord")
- `coord`: Coordinate axis index (0=X, 1=Y, 2=Z)
- `epsilon`: Tolerance value for coordinate comparison
- `normal_direction`: Normal direction filter (1=positive, -1=negative, 0=ignore)

## Predefined Camera Configurations

The script includes common camera viewpoints for standard orientations:

| View Name | Position | Description |
|-----------|----------|-------------|
| Top       | [0, 0, 16] | Looking down at the model |
| Side      | [14, 0, 1.3] | Looking at the model from the right side |
| Front     | [0, 14, 1.3] | Looking at the model from the front |
| Back      | [0, -14, 1.3] | Looking at the model from the back |
| Left      | [-14, 0, 1.3] | Looking at the model from the left side |
| Bottom    | [0, 0, -16] | Looking up at the model |

## Batch Processing

The batch processing mode will:

1. Scan the input directory for all `.ply` files
2. Process each file with the same camera configuration
3. Create corresponding `.glb` files in the output directory
4. Maintain the original filenames (with `.glb` extension)
5. Log the progress and results

This is ideal for processing multiple models with the same texture mapping configuration.

## Examples

### Example 1: Single File Processing

```bash
blender --background --python blender_mapper.py -- --single --input model.ply --config cameras.json --output model.glb
```

### Example 2: Batch Processing Multiple Models

```bash
blender --background --python blender_mapper.py -- --batch --input-dir ./raw_models --config cameras.json --output-dir ./processed_models --verbose
```

### Example 3: Six-sided Cube Mapping Configuration

```json
[
  {
    "name": "Camera_Top",
    "location": [0, 0, 10],
    "rotation": [0, 0, 0],
    "selection_params": {
      "type": "max_coord",
      "coord": 2,
      "normal_direction": 1
    },
    "material_index": 0,
    "texture_path": "./textures/top.png"
  },
  {
    "name": "Camera_Bottom",
    "location": [0, 0, -10],
    "rotation": [3.14159, 0, 0],
    "selection_params": {
      "type": "min_coord",
      "coord": 2,
      "normal_direction": -1
    },
    "material_index": 1,
    "texture_path": "./textures/bottom.png"
  },
  {
    "name": "Camera_Front",
    "location": [0, 10, 0],
    "rotation": [1.5708, 0, 0],
    "selection_params": {
      "type": "max_coord",
      "coord": 1,
      "normal_direction": 1
    },
    "material_index": 2,
    "texture_path": "./textures/front.png"
  },
  {
    "name": "Camera_Back",
    "location": [0, -10, 0],
    "rotation": [1.5708, 0, 3.14159],
    "selection_params": {
      "type": "min_coord",
      "coord": 1,
      "normal_direction": -1
    },
    "material_index": 3,
    "texture_path": "./textures/back.png"
  },
  {
    "name": "Camera_Right",
    "location": [10, 0, 0],
    "rotation": [1.5708, 0, 1.5708],
    "selection_params": {
      "type": "max_coord",
      "coord": 0,
      "normal_direction": 1
    },
    "material_index": 4,
    "texture_path": "./textures/right.png"
  },
  {
    "name": "Camera_Left",
    "location": [-10, 0, 0],
    "rotation": [1.5708, 0, -1.5708],
    "selection_params": {
      "type": "min_coord",
      "coord": 0,
      "normal_direction": -1
    },
    "material_index": 5,
    "texture_path": "./textures/left.png"
  }
]
```

## Troubleshooting

### Common Issues

1. **No faces selected**: Adjust the `epsilon` and `normal_direction` parameters
2. **Texture not visible**: Check texture file path and material assignment
3. **Distorted UVs**: Adjust camera position and rotation
4. **Memory issues in batch mode**: If processing large models, you may need to increase Blender's memory allocation

### Debug with Logging

Use the `--verbose` and `--log` options to get detailed information:

```bash
blender --background --python blender_mapper.py -- --batch --input-dir ./models --config config.json --output-dir ./output --verbose --log debug.log
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- [Blender Python API](https://docs.blender.org/api/current/index.html)
- [glTF 2.0 specification](https://github.com/KhronosGroup/glTF/tree/master/specification/2.0)

---

Created by [AN Jia Jun]
