import os
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session


load_dotenv(".env.backend")
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, echo=True)
app = FastAPI()
localSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)

db = localSession()


#TODO file seperation
class Base(DeclarativeBase):
    pass

class Profile(Base):
    __tablename__ = "Profiles"
    
    user_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    first_name: Mapped[str] = mapped_column()
    is_premium: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)


with Session(engine) as session:
    target = select(Profile).where(Profile.user_id == 1)
    result = session.scalars(target).first()

    if result:
        print(result.first_name)