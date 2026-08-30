#!/bin/bash
set +e
docker exec scout-nav bash -lc '
echo ===SAVE_MAP===
sed -n "70,150p" /Scout_mini_navigation/src/nav_api/fastapi_service/map_api.py
echo ===DOWNSAMPLE===
sed -n "228,270p" /Scout_mini_navigation/src/nav_api/fastapi_service/map_api.py
echo ===START_PCD===
sed -n "175,225p" /Scout_mini_navigation/src/nav_api/scripts/launch_manager.py
'
