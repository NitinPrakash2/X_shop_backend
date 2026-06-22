from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from src.shared.util.include_file.index import include_file
from src.db_config import engine, Base
import importlib.util, os as _os, sys as _sys


def _load_scheduler():
    if "xshop_scheduler" in _sys.modules:
        return _sys.modules["xshop_scheduler"]
    _path = _os.path.join(_os.path.dirname(__file__), "shared", "utility", "l", "xshop", "app", "services", "scheduler.py")
    _spec = importlib.util.spec_from_file_location("xshop_scheduler", _path)
    _mod  = importlib.util.module_from_spec(_spec)
    _sys.modules["xshop_scheduler"] = _mod
    _spec.loader.exec_module(_mod)
    return _mod


@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_scheduler().start_scheduler()
    yield
    _load_scheduler().stop_scheduler()


app = FastAPI(
    title="X Shop SaaS API",
    version="1.0.0",
    description="Multi-tenant SaaS platform for sellers to connect X (Twitter) accounts and manage X Shop.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.responses import HTMLResponse

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    return """
    <html><body style="font-family:sans-serif;padding:2rem">
    <h2>X Shop SaaS API</h2>
    <ul>
      <li><a href="/client-public/docs">Swagger — Public Routes</a> (register, login, oauth callback)</li>
      <li><a href="/client/docs">Swagger — Private Routes</a> (requires Bearer token)</li>
      <li><a href="/docs">Swagger — Main App</a></li>
    </ul>
    </body></html>
    """


from fastapi import Request as _Request
from fastapi.responses import RedirectResponse
from src.db_config import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

@app.get("/oauth/callback", include_in_schema=False)
async def x_oauth_callback_get(request: _Request, db: AsyncSession = Depends(get_db)):
    """Dedicated GET route for X OAuth callback - no query params in path"""
    code  = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")

    if error or not code or not state:
        return RedirectResponse(url=f"http://localhost:5173/xshop/login?error={error or 'missing_params'}")

    # Forward to frontend with code and state
    return RedirectResponse(url=f"http://localhost:5173/xshop/callback?code={code}&state={state}")




"""
# Create tables if not using Alembic
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
"""




# 🔐 Add middleware
#app.add_middleware(AuthMiddleware, token="secret-token")
#set..
#app.include_router(router, prefix="/admin") #router


#====party_1====#  [START]
def _party_1(_v={
    "party": str
}):
    _dta = {
        "app": {
        "global": app,
        "this_public":  FastAPI(title="X Shop API — Admin Public",  version="1.0.0", docs_url="/docs", redoc_url="/redoc"),
        "this_private": FastAPI(title="X Shop API — Admin Private", version="1.0.0", docs_url="/docs", redoc_url="/redoc"),
        },
        "prefix": "/admin",
        "prefix_public": "/admin-public",
    }
    AuthMiddleware_name, AuthMiddleware_module = include_file(f"src/parties/{_v["party"]}/middlewares/auth.py", lambda name, module: ())[0]
    AuthMiddleware = AuthMiddleware_module.AuthMiddleware 

    #set..
    include_file(f"src/parties/{_v["party"]}/routes",
        lambda name, 
        module: 
           (
            module.index({}) #_dta #print(name, module)
            #,print(module._ins['router']['public'])
            #set..
            #,_dta["app"]["this_public"].include_router(module._ins['router']['public'], prefix=_dta['prefix'])
            #,_dta["app"]["global"].include_router(module._ins['router']['public'], prefix="") # _dta['prefix']

            ,_dta["app"]["this_public"].include_router(module._ins['router']['public'], prefix="")

            ,_dta["app"]["this_private"].include_router(module._ins['router']['private'], prefix="" ) #_dta["prefix"]

            #set..
            #,_dta["app"]["global"].mount(_dta["prefix"], _dta["app"]["this_public"])


            #set..
            ,_dta["app"]["global"].mount(
                _dta["prefix_public"], 
                _dta["app"]["this_public"]
            )


            #set..
            ,_dta["app"]["global"].mount(
                _dta["prefix"], 
                _dta["app"]["this_private"]
            )

            #middleware
            ,_dta["app"]["this_private"].add_middleware(AuthMiddleware)
            
           )
    )
_party_1({
    "party": "party_1"
})
#====party_1====#  [END]




#====party_2====#  [START]
def _party_2(_v={
    "party": str
}):
    _dta = {
        "app": {
        "global": app,
        "this_public":  FastAPI(
            title="X Shop API — Public",
            version="1.0.0",
            description="Public endpoints: register, login, refresh_token, x_oauth_callback",
            docs_url="/docs",
            redoc_url="/redoc",
        ),
        "this_private": FastAPI(
            title="X Shop API — Private",
            version="1.0.0",
            description="Private endpoints (Bearer token required). All use POST with {action: ...} body.",
            docs_url="/docs",
            redoc_url="/redoc",
        ),
        },
        "prefix": "/client",
        "prefix_public": "/client-public",
    }
    AuthMiddleware_name, AuthMiddleware_module = include_file(f"src/parties/{_v["party"]}/middlewares/auth.py", lambda name, module: ())[0]
    AuthMiddleware = AuthMiddleware_module.AuthMiddleware 

    #set..
    include_file(f"src/parties/{_v["party"]}/routes",
        lambda name, 
        module: 
           (
            module.index({}) #_dta #print(name, module)
            #,print(module._ins['router']['public'])
            #set..
            #,_dta["app"]["this_public"].include_router(module._ins['router']['public'], prefix=_dta['prefix'])
            #,_dta["app"]["global"].include_router(module._ins['router']['public'], prefix="" ) # _dta['prefix']

            ,_dta["app"]["this_public"].include_router(module._ins['router']['public'], prefix="")

            ,_dta["app"]["this_private"].include_router(module._ins['router']['private'], prefix="" ) # _dta["prefix"]

            #set..
            #,_dta["app"]["global"].mount(_dta["prefix"], _dta["app"]["this_public"])


            #set..
            ,_dta["app"]["global"].mount(
                _dta["prefix_public"], 
                _dta["app"]["this_public"]
            )


            #set..
            ,_dta["app"]["global"].mount(
                _dta["prefix"], 
                _dta["app"]["this_private"]
            )

            #middleware
            ,_dta["app"]["this_private"].add_middleware(AuthMiddleware)
            
           )
    )
_party_2({
    "party": "party_2"
})
#====party_2====#  [END]




