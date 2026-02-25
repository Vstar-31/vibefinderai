vibefinderai-monorepo/
├── package.json           <-- The root file
├── frontend/              <-- React (Vite)
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── components/
│   │   ├── App.tsx
│   │   └── main.tsx
│   └── public/
└── backend/               <-- Python (FastAPI)
    ├── requirements.txt   <-- Python dependencies (FastAPI, Prisma, etc.)
    ├── main.py            <-- FastAPI core logic 
    ├── schema.prisma      <-- Database schema for Supabase
    └── routers/           <-- routes for AI, sync, and social 