import os
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pymongo import MongoClient
import bcrypt
import jwt
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="MediGuide Backend Engine")

# Enable CORS for React frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database Connection
client = MongoClient(os.getenv("MONGO_URI"))
db = client["mediguide_db"]
users_col = db["users"]
history_col = db["history"]

# Security Configurations
JWT_SECRET = os.getenv("JWT_SECRET")
ALGORITHM = "HS256"

# Pydantic Schemas
class UserAuth(BaseModel):
    username: str
    password: str

class SymptomInput(BaseModel):
    text: str
    language: str

class ChatInput(BaseModel):
    message: str

# --- AUTHENTICATION HELPER FUNCTIONS ---
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(username: str):
    expire = datetime.utcnow() + timedelta(hours=24)
    return jwt.encode({"sub": username, "exp": expire}, JWT_SECRET, algorithm=ALGORITHM)

def get_current_user(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return payload.get("sub")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session. Please log in.")

# --- ROUTING / ENDPOINTS ---

@app.post("/api/signup")
def signup(user: UserAuth):
    if users_col.find_one({"username": user.username}):
        raise HTTPException(status_code=400, detail="Username already exists.")
    
    hashed = hash_password(user.password)
    users_col.insert_one({"username": user.username, "password": hashed})
    return {"message": "Registration successful!"}

@app.post("/api/login")
def login(user: UserAuth):
    db_user = users_col.find_one({"username": user.username})
    if not db_user or not verify_password(user.password, db_user["password"]):
        raise HTTPException(status_code=400, detail="Incorrect username or password.")
    
    token = create_access_token(user.username)
    return {"token": token, "username": user.username}

@app.post("/api/predict")
def predict_disease(data: SymptomInput, token: str):
    username = get_current_user(token)
    text_lower = data.text.lower()
    
    # Advanced Rule-Based/NLP Triage Matrix (Simulating AI Engine outputs)
    if "chest pain" in text_lower or "breathing issue" in text_lower or "unconscious" in text_lower:
        disease = "Potential Cardiovascular / Respiratory Emergency"
        triage = "EMERGENCY"
        advice = "Critical condition detected. Please do not treat at home. Go to the nearest emergency hospital immediately."
    elif "fever" in text_lower or "cough" in text_lower or "days" in text_lower:
        disease = "Acute Respiratory Infection / Influenza-like Illness"
        triage = "MODERATE"
        advice = "Symptoms have persisted. Rest, stay hydrated, and schedule a consultation with a local doctor soon."
    else:
        disease = "Mild Viral Syndrome / Common Cold"
        triage = "HOME CARE"
        advice = "Safe to manage at home initially. Rest, drink warm fluids, and monitor symptoms closely."

    # Save to user search history
    history_entry = {
        "username": username,
        "input": data.text,
        "language": data.language,
        "predicted_disease": disease,
        "triage": triage,
        "advice": advice,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    }
    history_col.insert_one(history_entry)
    
    return history_entry

@app.post("/api/chatbot")
def personalized_chat(data: ChatInput, token: str):
    get_current_user(token) # Protect route
    # Simulated contextual conversational response
    msg = data.message.lower()
    if "diet" in msg or "eat" in msg:
        reply = "For general recovery, eat easily digestible foods like porridge, khichdi, and clear soups. Avoid oily foods."
    elif "fever" in msg:
        reply = "Keep track of temperatures. If it crosses 102°F or lasts over 3 days, see a medical professional."
    else:
        reply = "I am your MediGuide assistant. Keep sharing your symptoms, or ask about general wellness steps!"
    return {"reply": reply}

@app.get("/api/history")
def get_history(token: str):
    username = get_current_user(token)
    records = list(history_col.find({"username": username}, {"_id": 0}))
    return {"history": records[::-1]} # Return newest first

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)