# ReProfit — AI Profit Recovery & Reverse Logistics

🔗 **Live Demo:** [https://vercel.app](https://vercel.app)  
*(Note: Backend is hosted on Render's free tier; initial data load may take ~45 seconds while the server wakes up.)*

**ReProfit** is an AI-powered reverse logistics platform for e-commerce warehouses. It streamlines product return inspections using computer vision for product verification and condition assessment, automates resell/refurbish/recycle recommendations, and tracks recovered profit.

---

## Key Features
* **AI Condition & Product Verification:** Uses YOLO11 object detection (`yolo11n.pt`) to verify product categories and a custom YOLO11 classifier (`condition_yolo11.pt`) to evaluate item condition (`like_new`, `good`, `fair`, `damaged`, `poor`).
* **Interactive Return Queue:** Review AI recommendations, inspect confidence scores, and approve or reject return decisions.
* **Decision Engine & Analytics:** Configurable auto-processing thresholds, KPI dashboards, recovery trend charts, and CSV exports.
* **Live Marketplace Sourcing:** Search and import live product listings and pricing via **SerpApi** (Google Shopping) and the **eBay Browse API**, or bulk-upload via CSV.
* **Modern UI:** Responsive dark/light mode interface with global search and real-time notifications.

---

## Tech Stack
* **Frontend:** React 18, Vite, Tailwind CSS, TanStack Query, Axios, Recharts, React Router v6
* **Backend:** FastAPI, SQLAlchemy, SQLite, Pydantic, Pillow
* **Machine Learning:** Ultralytics YOLO11 (Object Detection & Condition Classification)

---

## Project Structure
```text
ReProfit_FullStack/
├── frontend/          # React + Vite client
├── backend/           # FastAPI server, ML inference & SQLite DB
└── README.md
```

---

## Local Setup

### 1. Backend
```bash
cd backend
python -m pip install -r requirements.txt
```
Create a `backend/.env` file with your API keys (optional for basic demo mode):
```env
SERPAPI_KEY=your-serpapi-key
EBAY_CLIENT_ID=your-ebay-app-id
EBAY_CLIENT_SECRET=your-ebay-cert-id
EBAY_ENVIRONMENT=production
EBAY_MARKETPLACE=EBAY_US
```
Start the server (`http://localhost:8000` | Docs at `/docs`):
```bash
python main.py
```

### 2. Frontend
```bash
cd frontend
npm install
```
Create a `frontend/.env` file:
```env
VITE_API_BASE_URL=http://localhost:8000/api
```
Start the dev server (`http://localhost:5173`):
```bash
npm run dev
```
