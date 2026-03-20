# backend/app/models/types.py
from pydantic import BaseModel, Field, ConfigDict
from pydantic.alias_generators import to_camel
from typing import List, Optional, Dict, Any, Literal
from enum import Enum
from datetime import datetime

class AgentStatus(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    ERROR = "ERROR"
    OFFLINE = "OFFLINE"
    ASSIGNED = "ASSIGNED"

class ReportingTarget(str, Enum):
    PARENT = "PARENT_AGENT"
    OWNER_DIRECT = "OWNER_DIRECT"
    BOTH = "HYBRID"

class HiveMindAccessLevel(str, Enum):
    ISOLATED = "ISOLATED"
    SHARED = "SHARED"
    GLOBAL = "GLOBAL"

class UserRole(str, Enum):
    GLOBAL_ADMIN = "GLOBAL_ADMIN"
    HIVE_ADMIN = "HIVE_ADMIN"
    HIVE_USER = "HIVE_USER"

class AgentRole(str, Enum):
    GENERIC = "generic"
    BUILDER = "builder"
    TESTER = "tester"
    REVIEWER = "reviewer"
    FIXER = "fixer"
    ARCHITECT = "architect"
    RESEARCHER = "researcher"

class OrgRole(str, Enum):
    CEO = "ceo"
    STRATEGY = "strategy"
    DEPARTMENT_HEAD = "department_head"
    MEMBER = "member"

ChannelType = Literal["telegram", "discord", "whatsapp", "slack", "custom"]

class ChannelCredentials(BaseModel):
    webhook_url: Optional[str] = None
    bot_token: Optional[str] = Field(None, alias="botToken")
    chat_id: Optional[str] = Field(None, alias="chatId")
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    client_id: Optional[str] = None
    mode: Optional[str] = None

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True
    )

class ChannelConfig(BaseModel):
    id: str
    type: ChannelType
    enabled: bool
    credentials: ChannelCredentials
    status: Literal["connected", "error", "disconnected"] = "disconnected"
    last_ping: Optional[datetime] = None

class FileEntry(BaseModel):
    id: str
    name: str
    type: str
    content: str
    size: int
    uploaded_at: datetime

class AgentMemory(BaseModel):
    short_term: List[str] = []
    summary: str = ""
    token_count: float = 0

class ReasoningConfig(BaseModel):
    model: str
    temperature: float = 0.7
    top_p: float = 1.0
    max_tokens: int = 150
    api_key: Optional[str] = None
    organization_id: Optional[str] = None
    cheap_model: Optional[str] = None
    use_global_default: bool = False
    use_custom_max_tokens: bool = False

class AgentSkill(BaseModel):
    agent_id: str
    skill_id: str
    skill_version_id: str
    installed_at: datetime
    config: Dict[str, Any] = {}
    enabled: bool = True

class MetaInfo(BaseModel):
    parent_agent: Optional[str] = None
    improved: bool = False
    simulation: bool = False
    mutation: Optional[str] = None
    last_evaluated: Optional[datetime] = None
    archived: bool = False
    archived_at: Optional[datetime] = None
    promoted_at: Optional[datetime] = None
    test_results: Optional[Dict[str, Any]] = None

class Agent(BaseModel):
    id: str
    name: str
    role: AgentRole
    soul_md: str = Field(alias="soulMd")
    identity_md: str = Field(alias="identityMd")
    tools_md: str = Field(alias="toolsMd")
    status: AgentStatus
    reasoning: ReasoningConfig
    reporting_target: ReportingTarget = ReportingTarget.PARENT
    parent_id: Optional[str] = None
    sub_agent_ids: List[str] = []
    channels: List[ChannelConfig] = []
    memory: AgentMemory
    last_active: datetime
    container_id: str
    user_uid: str
    local_files: List[FileEntry] = []
    skills: List[AgentSkill] = []
    meta: MetaInfo = Field(default_factory=MetaInfo)
    org_role: OrgRole = OrgRole.MEMBER
    department: Optional[str] = None

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        use_enum_values=True
    )

class Message(BaseModel):
    id: str
    from_agent: Optional[str] = Field(None, alias="from")
    to_agent: Optional[str] = Field(None, alias="to")
    content: str
    timestamp: datetime
    type: Optional[Literal["log", "chat", "internal", "error", "outbound"]] = None
    role: Optional[Literal["user", "model", "system"]] = None

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True
    )

class AgentCreate(BaseModel):
    name: str
    role: AgentRole = AgentRole.GENERIC
    soul_md: str = Field(alias="soulMd")
    identity_md: str = Field(alias="identityMd")
    tools_md: str = Field(alias="toolsMd")
    reasoning: ReasoningConfig
    reporting_target: ReportingTarget = ReportingTarget.PARENT
    parent_id: Optional[str] = None
    user_uid: Optional[str] = None
    channels: List[ChannelConfig] = []
    org_role: OrgRole = OrgRole.MEMBER
    department: Optional[str] = None

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        use_enum_values=True
    )

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[AgentRole] = None
    soul_md: Optional[str] = Field(None, alias="soulMd")
    identity_md: Optional[str] = Field(None, alias="identityMd")
    tools_md: Optional[str] = Field(None, alias="toolsMd")
    status: Optional[AgentStatus] = None
    reasoning: Optional[ReasoningConfig] = None
    reporting_target: Optional[ReportingTarget] = None
    parent_id: Optional[str] = None
    channels: Optional[List[ChannelConfig]] = None
    memory: Optional[AgentMemory] = None
    local_files: Optional[List[FileEntry]] = None
    meta: Optional[MetaInfo] = None
    org_role: Optional[OrgRole] = None
    department: Optional[str] = None

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        use_enum_values=True
    )

class ProviderModel(BaseModel):
    id: str
    name: str
    enabled: bool = False
    is_primary: bool = False
    is_utility: bool = False

class ProviderConfig(BaseModel):
    name: str
    display_name: str
    enabled: bool = False
    api_key_present: bool = False
    models: Dict[str, ProviderModel] = {}

class GlobalProviderConfig(BaseModel):
    providers: Dict[str, ProviderConfig] = {}

class ProviderConfigUpdate(BaseModel):
    provider: str
    enabled: Optional[bool] = None
    api_key: Optional[str] = None
    models: Optional[Dict[str, ProviderModel]] = None

class ProviderStatusResponse(BaseModel):
    providers: Dict[str, ProviderConfig]
    primary_model_id: Optional[str] = None
    utility_model_id: Optional[str] = None

class ConversationMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime

class HiveMindConfig(BaseModel):
    access_level: HiveMindAccessLevel = HiveMindAccessLevel.ISOLATED
    shared_hive_ids: List[str] = []

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        use_enum_values=True
    )

class Hive(BaseModel):
    id: str
    name: str
    description: str = ""
    agent_ids: List[str] = Field(default_factory=list, alias="agentIds")
    agents: List[Agent] = Field(default_factory=list, exclude=True)
    global_user_md: str = ""
    messages: List[Message] = []
    global_files: List[FileEntry] = []
    hive_mind_config: HiveMindConfig = HiveMindConfig()
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        use_enum_values=True,
    )

class HiveCreate(BaseModel):
    name: str
    description: str = ""
    global_user_md: str = ""

class HiveUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    global_user_md: Optional[str] = None
    hive_mind_config: Optional[HiveMindConfig] = None

class UserAccount(BaseModel):
    id: str
    username: str
    password_hash: str
    role: UserRole
    assigned_hive_ids: List[str] = []
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    password_changed: bool = False

class UserCreate(BaseModel):
    username: str
    password: str
    role: UserRole = UserRole.HIVE_USER
    assigned_hive_ids: List[str] = []

class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    role: Optional[UserRole] = None
    assigned_hive_ids: Optional[List[str]] = None

class UserLogin(BaseModel):
    username: str
    password: str

class GlobalSettings(BaseModel):
    login_enabled: bool = False
    session_timeout: int = 30
    system_name: str = "HiveBot Orchestrator"
    maintenance_mode: bool = False
    default_agent_uid: str = "10001"
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_period_seconds: int = 60

class HiveGoalStatus(str, Enum):
    CREATED = "created"
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"

class HiveGoal(BaseModel):
    id: str
    hive_id: str
    description: str
    constraints: Dict[str, Any] = {}
    success_criteria: List[str] = []
    status: HiveGoalStatus
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        use_enum_values=True
    )

class HiveTaskStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"

class HiveTask(BaseModel):
    id: str
    goal_id: str
    hive_id: str
    description: str
    agent_type: str
    status: HiveTaskStatus
    depends_on: List[str] = []
    required_skills: List[str] = []
    assigned_agent_id: Optional[str] = None
    input_data: Dict[str, Any] = {}
    output_data: Optional[Dict[str, Any]] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retries: int = 0

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        use_enum_values=True
    )

class HiveArtifact(BaseModel):
    id: str
    goal_id: str
    task_id: str
    file_path: str
    content: str
    version: int = 1
    status: str = "draft"
    created_at: datetime

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        use_enum_values=True
    )

class ExecutionLogLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    DEBUG = "debug"

class ExecutionLog(BaseModel):
    id: str
    goal_id: str
    task_id: Optional[str] = None
    agent_id: Optional[str] = None
    level: ExecutionLogLevel
    message: str
    iteration: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        use_enum_values=True
    )

class Currency(str, Enum):
    USD = "usd"
    EUR = "eur"
    GBP = "gbp"
    SIM = "sim"

class AccountType(str, Enum):
    HIVE = "hive"
    AGENT = "agent"
    SYSTEM = "system"

class TransactionType(str, Enum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRADE = "trade"
    FEE = "fee"
    TRANSFER = "transfer"

class TransactionStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class EconomyAccount(BaseModel):
    id: str
    owner_id: str
    owner_type: AccountType
    currency: Currency
    balance: float = 0.0
    created_at: datetime
    updated_at: datetime

class Transaction(BaseModel):
    id: str
    account_id: str
    type: TransactionType
    amount: float
    currency: Currency
    status: TransactionStatus
    description: Optional[str] = None
    metadata: Dict[str, Any] = {}
    created_at: datetime
    completed_at: Optional[datetime] = None

class StrategyType(str, Enum):
    TRADING = "trading"
    GROWTH = "growth"
    OPTIMIZATION = "optimization"

class Strategy(BaseModel):
    id: str
    name: str
    type: StrategyType
    owner_id: str
    owner_type: AccountType
    config: Dict[str, Any] = {}
    active: bool = True
    last_run: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

class RiskPolicy(BaseModel):
    id: str
    owner_id: str
    owner_type: AccountType
    max_loss_per_trade: float = 0.0
    max_daily_loss: float = 0.0
    max_position_size: float = 0.0
    kill_switch_enabled: bool = False
    kill_switch_triggered: bool = False
    created_at: datetime
    updated_at: datetime
