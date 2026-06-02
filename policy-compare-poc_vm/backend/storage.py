# backend/storage.py 
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, JSON 
from sqlalchemy.orm import declarative_base, sessionmaker 
from datetime import datetime 
import os 
 
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/demo.db") 
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}) 
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False) 
Base = declarative_base() 
 
class Document(Base): 
    __tablename__ = "documents" 
    id = Column(Integer, primary_key=True, index=True) 
    filename = Column(String, index=True) 
    text = Column(Text) 
    metadata = Column(JSON) 
    created_at = Column(DateTime, default=datetime.utcnow) 
 
class Audit(Base): 
    __tablename__ = "audit" 
    id = Column(Integer, primary_key=True, index=True) 
    user = Column(String) 
    action = Column(String) 
    target = Column(String) 
    details = Column(JSON) 
    timestamp = Column(DateTime, default=datetime.utcnow) 
 
def init_db(): 
    Base.metadata.create_all(bind=engine) 

    