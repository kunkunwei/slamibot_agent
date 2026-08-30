# -*- coding: utf-8 -*-
# 替换 global_localization.py 的 msg_to_array：改为按字段 offset 解析，点数取实际 data 长度
import io

path = r'F:\d360_nav2D\src\FAST_LIO_LOCALIZATION\scripts\global_localization.py'
data = io.open(path, 'r', encoding='utf-8', newline='').read()  # 保留 \r\n

old = (
    "def msg_to_array(pc_msg):\r\n"
    "    pc_array = ros_numpy.numpify(pc_msg)\r\n"
    "    pc = np.zeros([len(pc_array), 3])\r\n"
    "    pc[:, 0] = pc_array['x']\r\n"
    "    pc[:, 1] = pc_array['y']\r\n"
    "    pc[:, 2] = pc_array['z']\r\n"
    "    return pc\r\n"
)

new = (
    "def msg_to_array(pc_msg):\r\n"
    "    # FAST-LIO 的 /cloud_registered 偶发 width 与实际 data 点数不一致（消息缺陷），\r\n"
    "    # 且字段带 offset 间隙，ros_numpy 严格按 width reshape 会崩。\r\n"
    "    # 改为按字段 offset 解析、点数取实际 data 长度。\r\n"
    "    offsets = {f.name: f.offset for f in pc_msg.fields}\r\n"
    "    n = len(pc_msg.data) // pc_msg.point_step\r\n"
    "    dtype = np.dtype({\r\n"
    "        'names': ['x', 'y', 'z'],\r\n"
    "        'formats': ['<f4', '<f4', '<f4'],\r\n"
    "        'offsets': [offsets[k] for k in ('x', 'y', 'z')],\r\n"
    "        'itemsize': pc_msg.point_step,\r\n"
    "    })\r\n"
    "    arr = np.frombuffer(pc_msg.data, dtype=dtype, count=n)\r\n"
    "    return np.column_stack([arr['x'], arr['y'], arr['z']]).astype(np.float32)\r\n"
)

assert old in data, 'old block not found!'
data = data.replace(old, new)
io.open(path, 'w', encoding='utf-8', newline='').write(data)
print('replaced OK')
