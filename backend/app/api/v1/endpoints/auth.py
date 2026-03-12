from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel
from ....services.user_manager import UserManager
from ....core.config import settings
from ....models.types import GlobalSettings, UserUpdate
from ....core.rate_limit import check_rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])

# JWT settings
SECRET_KEY = settings.secrets.get("JWT_SECRET_KEY")
if not SECRET_KEY:
    import secrets
    SECRET_KEY = secrets.token_urlsafe(32)
    settings.secrets.set("JWT_SECRET_KEY", SECRET_KEY)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)

class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    username: str
    role: str
    password_changed: bool
    gateway_enabled: bool

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class UserInfo(BaseModel):
    id: str
    username: str
    role: str
    assigned_hive_ids: list[str]
    password_changed: bool
    created_at: datetime
    last_login: Optional[datetime]

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    from ....services.user_manager import UserManager  # avoid circular import
    
    # If login gateway is disabled, we don't need a token
    global_settings_data = settings.secrets.get("GLOBAL_SETTINGS")
    if global_settings_data:
        global_settings = GlobalSettings(**global_settings_data)
        if not global_settings.login_enabled:
            # Return the admin user (first GLOBAL_ADMIN)
            user_manager = UserManager()
            users = await user_manager.list_users()
            admin = next((u for u in users if u.role.value == "GLOBAL_ADMIN"), None)
            if admin:
                return admin
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No admin user found",
            )
    
    # Normal JWT authentication
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user_manager = UserManager()
    user = await user_manager.get_user(user_id)
    if user is None:
        raise credentials_exception
    return user

async def require_global_admin(current_user = Depends(get_current_user)):
    """Dependency to ensure user is a global admin."""
    if current_user.role.value != "GLOBAL_ADMIN":
        raise HTTPException(status_code=403, detail="Global admin required")
    return current_user

@router.post("/token", response_model=Token)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends()
):
    # Apply rate limiting
    await check_rate_limit(request, limit_key="login")

    user_manager = UserManager()
    user = await user_manager.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    await user_manager.update_last_login(user.id)
    access_token = create_access_token(data={"sub": user.id})
    
    # Get current gateway state
    global_settings_data = settings.secrets.get("GLOBAL_SETTINGS")
    gateway_enabled = True
    if global_settings_data:
        global_settings = GlobalSettings(**global_settings_data)
        gateway_enabled = global_settings.login_enabled
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        username=user.username,
        role=user.role.value,
        password_changed=user.password_changed,
        gateway_enabled=gateway_enabled
    )

@router.get("/no-auth-token", response_model=Token)
async def get_no_auth_token():
    """Get a token for the admin when gateway is disabled."""
    global_settings_data = settings.secrets.get("GLOBAL_SETTINGS")
    if global_settings_data:
        global_settings = GlobalSettings(**global_settings_data)
        if global_settings.login_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Gateway is enabled, use normal login"
            )
    
    user_manager = UserManager()
    users = await user_manager.list_users()
    admin = next((u for u in users if u.role.value == "GLOBAL_ADMIN"), None)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No admin user found"
        )
    
    access_token = create_access_token(data={"sub": admin.id})
    return Token(
        access_token=access_token,
        token_type="bearer",
        user_id=admin.id,
        username=admin.username,
        role=admin.role.value,
        password_changed=admin.password_changed,
        gateway_enabled=False
    )

@router.get("/me", response_model=UserInfo)
async def read_users_me(current_user = Depends(get_current_user)):
    return current_user

@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user = Depends(get_current_user)
):
    user_manager = UserManager()
    # If password hasn't been changed yet, allow setting without old password
    if not current_user.password_changed:
        # No need to verify old password
        update_data = UserUpdate(password=request.new_password)
        await user_manager.update_user(current_user.id, update_data)
    else:
        # Normal flow: verify old password
        if not user_manager.verify_password(request.old_password, current_user.password_hash):
            raise HTTPException(status_code=400, detail="Incorrect old password")
        update_data = UserUpdate(password=request.new_password)
        await user_manager.update_user(current_user.id, update_data)
    return {"msg": "Password changed successfully"}

@router.get("/gateway-state")
async def get_gateway_state():
    """Return whether the login gateway is enabled."""
    global_settings_data = settings.secrets.get("GLOBAL_SETTINGS")
    if global_settings_data:
        global_settings = GlobalSettings(**global_settings_data)
        return {"enabled": global_settings.login_enabled}
    return {"enabled": False}
