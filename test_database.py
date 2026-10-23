
from database import engine, Base
from models import ManualVersion, ManualSection

Base.metadata.create_all(bind=engine)

print("Database setup successful!")
print("ManualVersion table is ready!")
print("ManualSection table is ready!")


