-- nav_api 数据库表结构(MVP:地图表 + 点位表)
-- 说明:SQLite 为动态类型,String(N)/Float(15) 等长度精度约束在应用层校验,
--      此处仅保留数据库层能强制的约束(主键/唯一/外键/CHECK/默认值)。

-- ============================================================
-- Map 地图表
-- 点位/任务的 mapName 外键指向本表;本项目为纯 2D,mapType 用 2d_grid。
-- ============================================================
CREATE TABLE IF NOT EXISTS Map (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    mapName        TEXT    NOT NULL UNIQUE,                       -- 唯一,且不能为 'default'
    mapDisplayName TEXT,                                          -- 显示名(支持中文)
    mapDescription TEXT,                                          -- 地图描述
    mapType        TEXT    NOT NULL DEFAULT '2d_grid',            -- 3d_pointcloud / 2d_grid
    pcdFilePath    TEXT,                                          -- 3D 点云路径(本项目恒空)
    yamlFilePath   TEXT,                                          -- 2D 地图 .yaml 路径(关键)
    isActive       INTEGER NOT NULL DEFAULT 0,                    -- 1=当前激活地图(导航栈使用),0=未激活;通过 map/switch 切换
    createdTime    TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    updatedTime    TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    sort           INTEGER NOT NULL DEFAULT 0,
    CHECK (mapName <> 'default')
);

-- ============================================================
-- PointPosition 点位表
-- 同一地图下 pointName 唯一;坐标为 map 系(米),2D 场景 z=0、姿态仅 z/w。
-- ============================================================
CREATE TABLE IF NOT EXISTS PointPosition (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    type                INTEGER NOT NULL,                         -- PointType 枚举(巡检点=2)
    mapName             TEXT    NOT NULL,                         -- 关联 Map.mapName
    pointName           TEXT    NOT NULL,                         -- 同图内唯一
    positionX           REAL    NOT NULL,
    positionY           REAL    NOT NULL,
    positionZ           REAL    NOT NULL DEFAULT 0,
    orientationX        REAL    NOT NULL DEFAULT 0,
    orientationY        REAL    NOT NULL DEFAULT 0,
    orientationZ        REAL    NOT NULL DEFAULT 0,
    orientationW        REAL    NOT NULL DEFAULT 1,
    controlIp           TEXT,                                     -- 以下门控字段 MVP 留空
    controlPort         INTEGER,
    controlType         INTEGER,
    controlAddress      INTEGER,
    controlDelayClosure INTEGER,
    action              TEXT    DEFAULT '',
    actionContent       TEXT    DEFAULT '',
    sort                INTEGER NOT NULL DEFAULT 0,
    UNIQUE (mapName, pointName),
    FOREIGN KEY (mapName) REFERENCES Map(mapName)
);

-- ============================================================
-- TaskFlow 任务表(一条固定巡检路线)
-- 一个任务含 N 个有序点位(TaskPoint);删任务级联删其点位行,不碰 PointPosition。
-- ============================================================
CREATE TABLE IF NOT EXISTS TaskFlow (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    taskName    TEXT    NOT NULL,                            -- 同一地图下唯一
    description TEXT,
    mapName     TEXT    NOT NULL,                            -- 关联 Map.mapName
    isEnabled   INTEGER NOT NULL DEFAULT 1,                  -- 0/1 是否启用
    createdTime TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    updatedTime TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE (mapName, taskName),
    FOREIGN KEY (mapName) REFERENCES Map(mapName)
);

-- ============================================================
-- TaskPoint 任务点位表(引用模型)
-- 非临时点位:靠 pointId 软引用 PointPosition(不加强制外键),执行/展示时实时查;
--             点位被删则该站"失效",执行时报错。
-- 临时点位  :pointId 为空,坐标内联存本表。
-- ============================================================
CREATE TABLE IF NOT EXISTS TaskPoint (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    taskId        INTEGER NOT NULL,                          -- 关联 TaskFlow.id
    pointId       INTEGER,                                   -- 软引用 PointPosition.id;临时点位为 NULL
    pointName     TEXT    NOT NULL,                          -- 冗余:展示 + 点位被删后报错用
    type          INTEGER NOT NULL DEFAULT 2,                -- PointType 枚举
    pointOrder    INTEGER NOT NULL DEFAULT 0,                -- 执行顺序(避开 SQL 保留字 order)
    isTemporary   INTEGER NOT NULL DEFAULT 0,                -- 0/1 是否临时点位
    positionX     REAL,                                      -- 临时点位必填;非临时点位为空(实时查)
    positionY     REAL,
    positionZ     REAL,
    orientationX  REAL,
    orientationY  REAL,
    orientationZ  REAL,
    orientationW  REAL,
    action        TEXT    DEFAULT '',
    actionContent TEXT    DEFAULT '',
    FOREIGN KEY (taskId) REFERENCES TaskFlow(id) ON DELETE CASCADE
);

-- ============================================================
-- Area 区域表(电子围栏 / 巡检多边形)
-- 多边形顶点序列以 JSON 字符串存储,与前端 API 契约一致;
-- 同图内 areaName 唯一。
-- ============================================================
CREATE TABLE IF NOT EXISTS Area (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    areaName    TEXT    NOT NULL,
    mapName     TEXT    NOT NULL,
    description TEXT,
    type        INTEGER NOT NULL DEFAULT 0,
    points      TEXT    DEFAULT '[]',
    createdTime TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    updatedTime TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE (mapName, areaName),
    FOREIGN KEY (mapName) REFERENCES Map(mapName)
);

-- ============================================================
-- CycleConfig 周期执行配置表
-- 关联到 TaskFlow.id,描述一个任务以何种周期/次数重复执行。
-- cycleMode:0=按次,1=按日(cron 风格 HH:MM)。
-- ============================================================
CREATE TABLE IF NOT EXISTS CycleConfig (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    taskId        INTEGER NOT NULL,
    cycleMode     INTEGER NOT NULL DEFAULT 0,
    cycleInterval INTEGER NOT NULL DEFAULT 0,         -- 按次模式:每次间隔秒数
    cycleCount    INTEGER NOT NULL DEFAULT 0,         -- 0=无限;>0=本周期内最大执行次数
    startTime     TEXT,                                -- ISO 字符串,首次执行时间
    dailyTime     TEXT,                                -- 仅 cycleMode=1 时使用,形如 HH:MM
    isRunning     INTEGER NOT NULL DEFAULT 0,         -- 0/1 当前是否启用
    nextExecuteTime TEXT,                              -- 下次计划执行时间(ISO)
    createdTime   TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updatedTime   TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (taskId) REFERENCES TaskFlow(id) ON DELETE CASCADE
);

-- ============================================================
-- Captures 拍照记录表
-- 点位到点自动拍照 / 手动拍照的存档;文件实体在 CAPTURE_DIR,此处存元数据。
-- ============================================================
CREATE TABLE IF NOT EXISTS Captures (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    pointName   TEXT,                                           -- 关联点位名(手动拍照可为空)
    fileName    TEXT    NOT NULL,                               -- CAPTURE_DIR 下的文件名
    taskId      INTEGER,                                        -- 触发任务 ID(到点自动拍照时)
    source      TEXT    NOT NULL DEFAULT 'manual',              -- manual / point_action
    createdTime TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

-- ============================================================
-- NavigationAction 动作配置表
-- APP 动作界面使用的可配置动作清单,execute 按 code 分发到 photo/chassis 等
-- 类别对应的执行入口;未实现的类别返回清晰 unsupported 结果,绝不假装成功。
-- ============================================================
CREATE TABLE IF NOT EXISTS NavigationAction (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT    NOT NULL UNIQUE,                        -- 动作唯一编码(机器名,如 photo / stand_up)
    name        TEXT    NOT NULL,                               -- 中文显示名
    category    TEXT    NOT NULL DEFAULT 'other',               -- photo / chassis / other
    description TEXT    DEFAULT '',                             -- 动作说明
    content     TEXT    DEFAULT '',                             -- 动作执行内容(脚本/命令/参数体)
    parameters  TEXT    DEFAULT '',                             -- 动作附加参数(JSON 字符串)
    duration    INTEGER NOT NULL DEFAULT 0,                     -- 动作持续秒数(0=瞬时)
    enabled     INTEGER NOT NULL DEFAULT 1,                     -- 0/1 是否启用
    sort        INTEGER NOT NULL DEFAULT 0,                     -- APP 列表展示顺序
    createdTime TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    updatedTime TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

-- ============================================================
-- SystemConfig 系统配置表(key-value)
-- 持久化运行模式等启动参数,使容器/FastAPI 重启后能恢复上次的运行状态。
-- default_mode 取值: idle / mapping / navigation。
-- ============================================================
CREATE TABLE IF NOT EXISTS SystemConfig (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL DEFAULT '',
    updatedTime TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

