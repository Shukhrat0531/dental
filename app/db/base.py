from app.db.base_class import Base

# Alembic должен увидеть все модели
from app.models.user import User
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.payment import Payment
from app.models.clinic import Clinic
from app.models.procedure import Procedure
