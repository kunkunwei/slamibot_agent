docker exec -i scout-nav-product-9eebfd5-persistent-20260904 python3 - <<'PY'
import importlib.util, numpy as np, yaml
pcd='/var/lib/slamibot/scout-nav/maps/api_map/map0901/map0901.pcd'
yaml_path='/var/lib/slamibot/scout-nav/maps/api_map/map0901/map0901.yaml'
spec=importlib.util.spec_from_file_location('p2m','/Scout_mini_navigation/install/share/my_nav/maps/pcd_to_map.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
pts=m.read_pcd_xyz(pcd)
print('points', len(pts))
print('raw_min', np.round(pts.min(axis=0),4).tolist())
print('raw_max', np.round(pts.max(axis=0),4).tolist())
n,gz=m.fit_ground_normal(pts, thresh=0.05)
R=m.rotation_to_z(n)
leveled=pts @ R.T
print('ground_normal', np.round(n,6).tolist(), 'ground_z', float(gz))
print('R', np.round(R,6).tolist())
print('leveled_min', np.round(leveled.min(axis=0),4).tolist())
print('leveled_max', np.round(leveled.max(axis=0),4).tolist())
print('xy_delta_extent_raw', np.round(np.ptp(pts[:,:2],axis=0),4).tolist())
print('xy_delta_extent_leveled', np.round(np.ptp(leveled[:,:2],axis=0),4).tolist())
with open(yaml_path) as f: print('yaml', f.read())
PY