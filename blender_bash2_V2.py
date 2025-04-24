#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Blender Mapper - 多相机视角纹理映射工具

此脚本用于将多个纹理从不同相机视角映射到3D模型上。
使用JSON配置文件定义相机和纹理映射参数。

运行说明：
1、正常模式
/Applications/Blender.app/Contents/MacOS/Blender --background --python blender_mapper.py -- input.ply config.json output.glb
2、日志模式
/Applications/Blender.app/Contents/MacOS/Blender --background --python blender_mapper.py -- input.ply config.json output.glb --verbose --log processing.log
"""

import bpy
import os
import sys
import math
import bmesh
import json
import argparse
from mathutils import Vector
import logging
from typing import List, Dict, Tuple, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime

# 常量定义
SCRIPT_VERSION = "1.0.0"
DEFAULT_EPSILON = 1.5
DEFAULT_MATERIAL_BASENAME = "Material"
DEFAULT_UV_MAP_NAME = "UVMap"


# 设置日志记录器
class LoggerSetup:
    """日志设置类"""

    @staticmethod
    def setup(level: int = logging.INFO, log_file: Optional[str] = None) -> logging.Logger:
        """配置并返回日志记录器"""
        # 获取或创建logger
        logger = logging.getLogger("blender_mapper")

        # 防止日志重复：检查是否已经配置过
        if logger.handlers:
            return logger

        # 设置级别
        logger.setLevel(level)

        # 阻止日志传播到父logger(root logger)
        logger.propagate = False

        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        # 如果指定了日志文件，创建文件处理器
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(level)
            file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)

        return logger


# 创建日志记录器
logger = LoggerSetup.setup()


@dataclass
class SelectionParams:
    """面选择参数数据类"""
    type: str = "max_coord"  # 选择类型: max_coord, min_coord, custom
    coord: int = 2  # 坐标轴索引: 0=X, 1=Y, 2=Z
    epsilon: float = DEFAULT_EPSILON  # 容差值
    normal_direction: int = 1  # 法线方向: 1=正, -1=负, 0=忽略

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SelectionParams':
        """从字典创建选择参数对象"""
        return cls(
            type=data.get("type", "max_coord"),
            coord=data.get("coord", 2),
            epsilon=data.get("epsilon", DEFAULT_EPSILON),
            normal_direction=data.get("normal_direction", 1)
        )


@dataclass
class CameraConfig:
    """相机配置数据类"""
    name: str  # 相机名称
    location: Tuple[float, float, float]  # 位置坐标
    rotation: Tuple[float, float, float]  # 旋转角度（弧度）
    selection_params: SelectionParams  # 面选择参数
    material_index: int  # 材质索引
    texture_path: str  # 纹理路径

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CameraConfig':
        """从字典创建相机配置对象"""
        selection_params = SelectionParams.from_dict(data.get("selection_params", {}))
        return cls(
            name=data.get("name", "Camera"),
            location=tuple(data.get("location", (0, 0, 10))),
            rotation=tuple(data.get("rotation", (0, 0, 0))),
            selection_params=selection_params,
            material_index=data.get("material_index", 0),
            texture_path=data.get("texture_path", "")
        )

    def validate(self) -> bool:
        """验证相机配置是否有效"""
        if not os.path.exists(self.texture_path):
            logger.error(f"纹理文件不存在: {self.texture_path}")
            return False
        return True


class BlenderHelper:
    """Blender操作辅助类"""

    @staticmethod
    def add_camera(name: str, location: Tuple[float, float, float],
                   rotation: Tuple[float, float, float]) -> bpy.types.Object:
        """添加并配置一个相机"""
        bpy.ops.object.camera_add(
            enter_editmode=False,
            align='WORLD',
            location=location,
            rotation=rotation,
            scale=(1, 1, 1)
        )
        camera = bpy.context.active_object
        camera.name = name
        logger.info(f"添加相机: {name}, 位置: {location}, 旋转: {rotation}")
        return camera

    @staticmethod
    def setup_material_with_texture(obj: bpy.types.Object,
                                    material_index: int,
                                    texture_path: str,
                                    material_name: str) -> bpy.types.Material:
        """设置材质并应用纹理"""
        # 确保有足够的材质槽
        while len(obj.material_slots) <= material_index:
            obj.data.materials.append(None)

        # 创建或重用材质
        if obj.material_slots[material_index].material:
            mat = obj.material_slots[material_index].material
            mat.name = material_name
            logger.info(f"使用现有材质: {material_name}")
        else:
            # 创建新材质
            mat = bpy.data.materials.new(name=material_name)
            obj.material_slots[material_index].material = mat
            logger.info(f"创建新材质: {material_name}")

        # 设置材质节点
        mat.use_nodes = True
        nodes = mat.node_tree.nodes

        # 清除默认节点
        for node in nodes:
            nodes.remove(node)

        # 创建着色器节点
        bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
        bsdf.location = (300, 0)

        output = nodes.new(type='ShaderNodeOutputMaterial')
        output.location = (500, 0)

        mat.node_tree.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

        # 加载纹理
        try:
            # 检查是否已加载此图像
            existing_image = None
            for img in bpy.data.images:
                if img.filepath == texture_path:
                    existing_image = img
                    break

            if existing_image:
                img = existing_image
                logger.info(f"使用已加载的纹理: {texture_path}")
            else:
                img = bpy.data.images.load(filepath=texture_path)
                logger.info(f"加载新纹理: {texture_path}")

            tex_img = nodes.new(type='ShaderNodeTexImage')
            tex_img.location = (0, 0)
            tex_img.image = img

            # 连接纹理到着色器
            mat.node_tree.links.new(tex_img.outputs['Color'], bsdf.inputs['Base Color'])

            logger.info(f"已应用纹理 {texture_path} 到材质 {material_name}")

        except Exception as e:
            logger.error(f"加载纹理 {texture_path} 失败: {e}")

        return mat


class UVProjector:
    """UV投影工具类"""

    @staticmethod
    def project_from_view_manual(obj: bpy.types.Object, camera: bpy.types.Object) -> bool:
        """基于透视相机进行精确UV投影"""
        logger.info(f"基于相机 {camera.name} 计算UV投影")

        # 确保在编辑模式
        if obj.mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')

        mesh = obj.data
        bm = bmesh.from_edit_mesh(mesh)

        # 获取UV层
        uv_layer = bm.loops.layers.uv.verify()

        # 获取相机参数
        cam_data = camera.data
        is_persp = cam_data.type == 'PERSP'  # 确认是透视相机

        # 获取相机到世界的转换矩阵及其逆矩阵
        cam_matrix_world = camera.matrix_world
        cam_matrix_world_inv = cam_matrix_world.inverted()

        # 获取选中的面
        selected_faces = [f for f in bm.faces if f.select]
        if not selected_faces:
            logger.warning("没有选中的面，无法进行UV投影")
            return False

        # 输出调试信息
        logger.info(f"相机类型: {'透视' if is_persp else '正交'}, 选中面数量: {len(selected_faces)}")

        # 为透视相机获取视野和宽高比
        if is_persp:
            sensor_width = cam_data.sensor_width
            sensor_height = cam_data.sensor_height
            focal_length = cam_data.lens

            # 计算视野 (FOV)
            fov = 2 * math.atan(sensor_width / (2 * focal_length))
            aspect_ratio = sensor_width / sensor_height

            logger.info(f"焦距: {focal_length}mm, 视野: {math.degrees(fov):.1f}°, 宽高比: {aspect_ratio:.2f}")

        # 应用UV坐标
        for face in selected_faces:
            for loop in face.loops:
                # 获取顶点的全局坐标
                vert_global = obj.matrix_world @ loop.vert.co

                # 将顶点转换到相机空间
                vert_view = cam_matrix_world_inv @ vert_global

                # 针对透视相机的UV计算
                if is_persp:
                    # 透视投影 - 与Blender内部算法更接近
                    # z轴指向相机后方，所以需要用-z
                    if vert_view.z < 0:  # 确保在相机前方（z为负值表示在相机前方）
                        # 透视除法
                        screen_x = vert_view.x / -vert_view.z
                        screen_y = vert_view.y / -vert_view.z

                        # 根据视野和宽高比调整
                        fov_factor = math.tan(fov / 2)
                        u = 0.5 + screen_x / (2 * fov_factor * aspect_ratio)
                        v = 0.5 + screen_y / (2 * fov_factor)
                    else:
                        # 如果顶点在相机后面，设置默认值
                        u, v = 0.5, 0.5
                else:
                    # 正交投影（以防相机类型不是透视）
                    u = 0.5 + vert_view.x / 10.0
                    v = 0.5 + vert_view.y / 10.0

                # 设置UV坐标
                loop[uv_layer].uv = (u, v)

        # 更新网格
        bmesh.update_edit_mesh(mesh)
        logger.info("UV投影计算完成")
        return True


class FaceSelector:
    """面选择工具类"""

    @staticmethod
    def select_faces_by_criteria(obj: bpy.types.Object,
                                 selection_params: SelectionParams) -> int:
        """
        通用面选择函数

        参数:
        - obj: Blender对象
        - selection_params: 选择参数

        返回:
        - 选中的面数量
        """
        bm = bmesh.from_edit_mesh(obj.data)
        matrix_world = obj.matrix_world

        # 取消选择所有面
        for face in bm.faces:
            face.select = False

        selection_type = selection_params.type
        coord_index = selection_params.coord
        epsilon = selection_params.epsilon
        normal_direction = selection_params.normal_direction

        # 坐标轴名称用于日志
        axis_name = ['X', 'Y', 'Z'][coord_index]

        selected_count = 0

        if selection_type == 'max_coord':
            # 基于最大坐标值选择面
            max_coord = max((matrix_world @ v.co)[coord_index] for v in bm.verts)
            logger.info(f"最大{axis_name}坐标值: {max_coord}")

            # 选择满足条件的面
            for face in bm.faces:
                verts_world_coords = [(matrix_world @ v.co)[coord_index] for v in face.verts]

                # 检查是否所有顶点都接近最大值
                if all(coord >= max_coord - epsilon for coord in verts_world_coords):
                    # 检查法线方向（如果需要）
                    if normal_direction != 0:
                        normal_world = matrix_world.to_3x3() @ face.normal
                        # 检查法线是否指向指定方向
                        if (normal_direction > 0 and normal_world[coord_index] > 0) or \
                                (normal_direction < 0 and normal_world[coord_index] < 0):
                            face.select = True
                            selected_count += 1
                    else:
                        face.select = True
                        selected_count += 1

            logger.info(f"已选择 {selected_count} 个面（基于{axis_name}坐标最大值）")

        elif selection_type == 'min_coord':
            # 基于最小坐标值选择面
            min_coord = min((matrix_world @ v.co)[coord_index] for v in bm.verts)
            logger.info(f"最小{axis_name}坐标值: {min_coord}")

            # 选择满足条件的面
            for face in bm.faces:
                verts_world_coords = [(matrix_world @ v.co)[coord_index] for v in face.verts]

                # 检查是否所有顶点都接近最小值
                if all(coord <= min_coord + epsilon for coord in verts_world_coords):
                    # 检查法线方向（如果需要）
                    if normal_direction != 0:
                        normal_world = matrix_world.to_3x3() @ face.normal
                        # 检查法线是否指向指定方向
                        if (normal_direction > 0 and normal_world[coord_index] > 0) or \
                                (normal_direction < 0 and normal_world[coord_index] < 0):
                            face.select = True
                            selected_count += 1
                    else:
                        face.select = True
                        selected_count += 1

            logger.info(f"已选择 {selected_count} 个面（基于{axis_name}坐标最小值）")

        elif selection_type == 'custom':
            # 这里可以添加其他自定义的选择逻辑
            logger.warning("自定义选择类型尚未实现")

        else:
            logger.warning(f"未知的选择类型: {selection_type}")

        # 更新网格
        bmesh.update_edit_mesh(obj.data)
        return selected_count


class ConfigManager:
    """配置管理类"""

    @staticmethod
    def load_camera_configs(config_file: str) -> List[CameraConfig]:
        """从JSON文件加载相机配置"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            configs = []
            for item in data:
                config = CameraConfig.from_dict(item)
                configs.append(config)

            logger.info(f"从配置文件加载了 {len(configs)} 个相机配置")
            return configs

        except json.JSONDecodeError as e:
            logger.error(f"解析JSON配置文件失败: {e}")
            raise
        except Exception as e:
            logger.error(f"加载配置文件时出错: {e}")
            raise


class TextureMapper:
    """纹理映射处理类"""

    def __init__(self, input_ply: str, configs: List[CameraConfig], output_glb: str):
        """初始化纹理映射器"""
        self.input_ply = input_ply
        self.configs = configs
        self.output_glb = output_glb
        self.cameras = {}  # 存储相机对象的字典

    def validate_configs(self) -> bool:
        """验证所有配置"""
        if not os.path.exists(self.input_ply):
            logger.error(f"输入PLY文件不存在: {self.input_ply}")
            return False

        # 验证所有相机配置
        for config in self.configs:
            if not config.validate():
                return False

        return True

    def setup_scene(self) -> Optional[bpy.types.Object]:
        """设置场景和导入模型"""
        try:
            # 清除默认对象
            bpy.ops.object.select_all(action='SELECT')
            bpy.ops.object.delete()

            # 导入PLY文件
            logger.info(f"导入PLY文件: {self.input_ply}")
            bpy.ops.wm.ply_import(filepath=self.input_ply, files=[{"name": os.path.basename(self.input_ply)}])

            # 添加所有相机
            for config in self.configs:
                self.cameras[config.name] = BlenderHelper.add_camera(
                    config.name,
                    config.location,
                    config.rotation
                )

            # 寻找网格对象
            mesh_obj = None
            for obj in bpy.context.scene.objects:
                if obj.type == 'MESH':
                    mesh_obj = obj
                    obj.select_set(True)
                    bpy.context.view_layer.objects.active = obj
                    break

            if not mesh_obj:
                logger.error("场景中找不到网格对象")
                return None

            # 确保有UV层
            if not mesh_obj.data.uv_layers:
                mesh_obj.data.uv_layers.new(name=DEFAULT_UV_MAP_NAME)
                logger.info(f"创建了新的UV层: {DEFAULT_UV_MAP_NAME}")

            return mesh_obj

        except Exception as e:
            logger.error(f"设置场景时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def process_camera_view(self, obj: bpy.types.Object, config: CameraConfig) -> bool:
        """处理单个相机视角"""
        try:
            logger.info(f"开始处理相机 {config.name}")

            # 获取相机对象
            camera = self.cameras.get(config.name)
            if not camera:
                logger.error(f"找不到相机: {config.name}")
                return False

            # 设置为当前活动相机
            bpy.context.scene.camera = camera

            # 选择面
            bpy.ops.object.mode_set(mode='EDIT')
            selected_count = FaceSelector.select_faces_by_criteria(obj, config.selection_params)

            if selected_count == 0:
                logger.warning(f"相机 {config.name} 没有选中任何面")
                return False

            # 设置材质
            material_name = f"{DEFAULT_MATERIAL_BASENAME}_{config.name}"
            BlenderHelper.setup_material_with_texture(
                obj,
                config.material_index,
                config.texture_path,
                material_name
            )

            # 分配材质
            obj.active_material_index = config.material_index
            bpy.ops.object.material_slot_assign()

            # UV投影
            UVProjector.project_from_view_manual(obj, camera)

            return True

        except Exception as e:
            logger.error(f"处理相机视角 {config.name} 时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def process(self) -> bool:
        """处理模型和所有相机视角"""
        try:
            logger.info(f"开始处理模型 {self.input_ply} 使用 {len(self.configs)} 个相机配置")

            # 验证配置
            if not self.validate_configs():
                return False

            # 设置场景和导入模型
            mesh_obj = self.setup_scene()
            if not mesh_obj:
                return False

            # 处理每个相机配置
            for config in self.configs:
                self.process_camera_view(mesh_obj, config)

            # 切换回对象模式
            bpy.ops.object.mode_set(mode='OBJECT')

            # 导出GLB
            logger.info(f"导出到GLB: {self.output_glb}")
            bpy.ops.export_scene.gltf(filepath=self.output_glb, export_format='GLB')

            logger.info("处理成功完成")
            return True

        except Exception as e:
            logger.error(f"处理模型时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description=f"Blender多相机纹理映射工具 v{SCRIPT_VERSION}",
        epilog="示例: blender --background --python %(prog)s -- input.ply config.json output.glb",
        add_help=False  # 禁用默认帮助，因为Blender有自己的--help参数
    )

    # 添加参数前的自定义帮助文本
    if '--help' in sys.argv or '-h' in sys.argv:
        print(f"Blender多相机纹理映射工具 v{SCRIPT_VERSION}")
        print("用法: blender --background --python script.py -- [参数]")
        print("\n参数:")
        print("  input.ply    输入PLY文件路径")
        print("  config.json  相机配置JSON文件路径")
        print("  output.glb   输出GLB文件路径")
        print("\n配置文件示例:")
        print('''{
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
  "texture_path": "/path/to/texture.png"
}''')
        sys.exit(0)

    # 仅处理Blender传递的参数（在 -- 之后的参数）
    argv = sys.argv
    try:
        argv = argv[argv.index("--") + 1:]
    except ValueError:
        argv = []

    # 添加位置参数
    parser.add_argument('input_ply', help='输入PLY文件路径')
    parser.add_argument('config_json', help='相机配置JSON文件路径')
    parser.add_argument('output_glb', help='输出GLB文件路径')

    # 添加可选参数
    parser.add_argument('--log', help='日志文件路径')
    parser.add_argument('--verbose', '-v', action='store_true', help='显示详细日志')

    # 解析参数
    args = parser.parse_args(argv)
    return args


def main():
    """主函数"""
    print(f"Blender多相机纹理映射工具 v{SCRIPT_VERSION}")

    try:
        # 解析命令行参数
        args = parse_arguments()

        # 设置日志级别
        log_level = logging.DEBUG if args.verbose else logging.INFO
        global logger
        logger = LoggerSetup.setup(level=log_level, log_file=args.log)

        # 记录开始时间
        start_time = datetime.now()
        logger.info(f"开始执行: {start_time}")

        # 加载相机配置
        camera_configs = ConfigManager.load_camera_configs(args.config_json)

        # 创建并执行纹理映射器
        mapper = TextureMapper(args.input_ply, camera_configs, args.output_glb)
        success = mapper.process()

        # 记录结束时间和总用时
        end_time = datetime.now()
        duration = end_time - start_time
        logger.info(f"执行结束: {end_time}")
        logger.info(f"总用时: {duration}")

        # 返回适当的退出代码
        sys.exit(0 if success else 1)

    except Exception as e:
        logger.error(f"执行过程中发生错误: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


# 当直接作为脚本运行时
if __name__ == "__main__":
    main()