"""Action catalog and execution APIs used by the navigation clients."""
from fastapi import APIRouter
from .database import get_conn
from .models import ApiResponse, NavigationActionAddRequest, NavigationActionUpdateRequest, NavigationActionDeleteRequest, NavigationActionToggleRequest, NavigationActionExecuteRequest, fail, ok

router = APIRouter(prefix="/api/action", tags=["动作管理"])
DEFAULTS = [
    ("photo", "拍照", "拍照动作", "other", "", "", None, 1, 0),
    ("stand_down", "趴下", "底盘动作（需运行时支持）", "chassis", "", "", None, 1, 1),
    ("sit_down", "坐下", "底盘动作（需运行时支持）", "chassis", "", "", None, 1, 2),
    ("hello", "打招呼", "底盘动作（需运行时支持）", "chassis", "", "", None, 1, 3),
    ("stretch", "伸展", "底盘动作（需运行时支持）", "chassis", "", "", None, 1, 4),
    ("stand_up", "恢复站立", "底盘动作（需运行时支持）", "chassis", "", "", None, 1, 5),
]

def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS NavigationAction (
      id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL UNIQUE,
      name TEXT NOT NULL, category TEXT NOT NULL DEFAULT 'other',
      description TEXT DEFAULT '', content TEXT DEFAULT '', parameters TEXT DEFAULT '',
      duration REAL, enabled INTEGER NOT NULL DEFAULT 1, sort INTEGER NOT NULL DEFAULT 0,
      createdTime TEXT NOT NULL DEFAULT (datetime('now','localtime')),
      updatedTime TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    )""")
    for row in DEFAULTS:
        conn.execute("INSERT OR IGNORE INTO NavigationAction(code,name,description,category,content,parameters,duration,enabled,sort) VALUES (?,?,?,?,?,?,?,?,?)", row)

def _row(r):
    return {k: r[k] for k in r.keys()}

@router.get("/list", response_model=ApiResponse)
def list_actions():
    with get_conn() as conn:
        _ensure_table(conn)
        rows = conn.execute("SELECT id,code,name,description,content,parameters,duration,enabled,sort FROM NavigationAction ORDER BY sort,id").fetchall()
    return ok([_row(r) for r in rows])

@router.post("/add", response_model=ApiResponse)
def add_action(req: NavigationActionAddRequest):
    with get_conn() as conn:
        _ensure_table(conn)
        try:
            cur = conn.execute("INSERT INTO NavigationAction(code,name,category,description,content,parameters,duration,enabled,sort) VALUES (?,?,?,?,?,?,?,?,?)", (req.code,req.name,req.category,req.description or '',getattr(req,'content',''),getattr(req,'parameters',''),getattr(req,'duration',None),req.enabled,99))
        except Exception as exc:
            return fail("动作新增失败: %s" % exc)
        row = conn.execute("SELECT * FROM NavigationAction WHERE id=?", (cur.lastrowid,)).fetchone()
    return ok(_row(row), "动作已添加")

@router.post("/update", response_model=ApiResponse)
def update_action(req: NavigationActionUpdateRequest):
    fields=[]; vals=[]
    for name in ("name","category","description","enabled"):
        value=getattr(req,name,None)
        if value is not None: fields.append(name+"=?"); vals.append(value)
    if not fields: return fail("没有可更新字段")
    fields.append("updatedTime=datetime('now','localtime')"); vals.append(req.id)
    with get_conn() as conn:
        _ensure_table(conn); cur=conn.execute("UPDATE NavigationAction SET "+",".join(fields)+" WHERE id=?", vals)
        if cur.rowcount==0: return fail("动作不存在")
        row=conn.execute("SELECT * FROM NavigationAction WHERE id=?",(req.id,)).fetchone()
    return ok(_row(row), "动作已更新")

@router.post("/delete", response_model=ApiResponse)
def delete_action(req: NavigationActionDeleteRequest):
    with get_conn() as conn:
        _ensure_table(conn); cur=conn.execute("DELETE FROM NavigationAction WHERE id=?",(req.id,))
    return ok(None, "动作已删除") if cur.rowcount else fail("动作不存在")

@router.post("/toggle", response_model=ApiResponse)
def toggle_action(req: NavigationActionToggleRequest):
    with get_conn() as conn:
        _ensure_table(conn); cur=conn.execute("UPDATE NavigationAction SET enabled=?,updatedTime=datetime('now','localtime') WHERE id=?",(req.enabled,req.id))
    return ok(None, "动作已启用" if req.enabled else "动作已禁用") if cur.rowcount else fail("动作不存在")

@router.post("/execute", response_model=ApiResponse)
def execute_action(req: NavigationActionExecuteRequest):
    with get_conn() as conn:
        _ensure_table(conn); row=conn.execute("SELECT * FROM NavigationAction WHERE code=? AND enabled=1",(req.action,)).fetchone()
    if row is None: return fail("动作不存在或已禁用")
    return fail("动作暂未实现: %s" % req.action, {"action": req.action, "supported": False})

@router.post("/stop", response_model=ApiResponse)
def stop_action():
    return fail("动作停止暂未实现", {"supported": False})
