# shared/database package
from .connection import DatabaseConnection
from .providers import ProvidersRepository
from .payments import PaymentsRepository
from .verification import VerificationRepository
from .portal import PortalRepository
from .safety import SafetyRepository
from .analytics import AnalyticsRepository
from .trials import TrialsRepository
from .migrations import MigrationsRepository

class Database:
    """Facade for all database repositories."""
    def __init__(self):
        self.manager = DatabaseConnection()
        self.providers = ProvidersRepository(self.manager)
        self.payments = PaymentsRepository(self.manager)
        self.verification = VerificationRepository(self.manager)
        self.portal = PortalRepository(self.manager)
        self.safety = SafetyRepository(self.manager)
        self.analytics = AnalyticsRepository(self.manager)
        self.trials = TrialsRepository(self.manager)
        self.migrations = MigrationsRepository(self.manager)
