# InsightFlow — Decision Intelligence System

> Upload any CSV → get ranked, explainable insights with statistical analysis and auto-generated visualizations.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────┐
│  Frontend (Next.js + Tailwind + Recharts)   │
│  Port 3000                                  │
├─────────────────────────────────────────────┤
│  POST /analyze (CSV file)                   │
│  GET  /history                              │
│  GET  /health                               │
├─────────────────────────────────────────────┤
│  Backend (FastAPI + pandas + SQLAlchemy)     │
│  Port 8000                                  │
├──────────┬──────────────┬───────────────────┤
│ Analyzer │ Rule Engine  │ Visualizer        │
│ (pandas) │ (20 rules)   │ (matplotlib)      │
├──────────┴──────────────┴───────────────────┤
│  SQLite Database                            │
└─────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Backend
```bash
cd backend
pip install -r requirements.txt
python run.py
# → http://localhost:8000/docs (Swagger UI)
```

### Frontend
```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

## 📊 Features (Week 1)

- **Drag & drop CSV upload** with file validation
- **Auto-generated statistics** for every column (mean, median, std, skewness)
- **20-rule insight engine** with severity ranking (Critical → Warning → Info)
- **Auto-generated charts**: correlation heatmap, missing values, distributions, box plots
- **Interactive Recharts** for exploring distributions
- **Upload history** stored in SQLite
- **Premium dark theme** with glassmorphism effects

## 🧠 The 20 Insight Rules

| # | Rule | Severity |
|---|------|----------|
| 1 | Missing > 40% | Critical |
| 2 | Missing 20-40% | Warning |
| 3 | Missing 5-20% | Info |
| 4 | High skewness > 2.0 | Warning |
| 5 | Moderate skewness 1-2 | Info |
| 6 | Correlation > 0.90 | Critical |
| 7 | Correlation 0.75-0.90 | Warning |
| 8 | Zero variance column | Critical |
| 9 | Outliers > 3σ | Warning |
| 10 | High cardinality (>50 unique) | Warning |
| 11 | Datetime column detected | Info |
| 12 | Integer might be categorical | Info |
| 13 | Negative values in positive column | Warning |
| 14 | Class imbalance > 5:1 | Warning |
| 15 | Duplicate rows > 5% | Warning |
| 16 | Dominant value > 95% | Warning |
| 17 | Small dataset < 50 rows | Warning |
| 18 | Wide dataset (cols > rows) | Info |
| 19 | Perfect correlation r=1.0 | Critical |
| 20 | Entirely empty column | Critical |

## 🛠️ Tech Stack

- **Backend**: Python, FastAPI, pandas, scipy, matplotlib, seaborn, SQLAlchemy
- **Frontend**: Next.js 15, React, Tailwind CSS, Recharts, Lucide Icons
- **Database**: SQLite (will upgrade to PostgreSQL in Week 4)

## 📅 Roadmap

- [x] Week 1: Foundation (CSV analysis, rule engine, visualizations)
- [ ] Week 2: LangGraph 4-node intelligence pipeline
- [ ] Week 3: ML features (Isolation Forest, SHAP, STL decomposition)
- [ ] Week 4: RAG + "Why this answer?" panel
- [ ] Week 5: Deploy + Resume + Outreach
