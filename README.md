# vibefinderai
AI Music discovery and playlist generation platform
graph TD
    %% --- User Interaction ---
    User((User))
    
    %% --- Frontend (Vercel) ---
    subgraph Frontend [React Frontend - Vercel Hobby Tier]
        UI_Auth[Multi-OAuth Login]
        UI_Hybrid[Hybrid UI Prompt Form\nSliders + Text]
        UI_Player[Cross-Platform Web Player\nAudio Visualizer]
        UI_Social[Forum & Smartlinks]
    end

    %% --- Backend (Render) ---
    subgraph Backend [Node.js/Express Backend - Render Free Tier]
        API_Gateway{API Router}
        
        Auth_Service[Auth Service\nSuperTokens/Passport]
        
        AI_Orchestrator[LangChain Agent\nText2Tracks Engine]
        
        Sync_Service[ISRC Disambiguation Engine\nCross-Platform Matcher]
        
        Social_Service[Forum & Playlist\nCRUD Controllers]
    end

    %% --- Database (Supabase/Neon) ---
    subgraph Database [PostgreSQL - Supabase Free Tier]
        DB_Users[(Users & OAuthIdentities)]
        DB_Playlists[(Playlists & Tracks)]
        DB_Social[(Forums & Comments)]
    end

    %% --- External APIs ---
    subgraph External [External APIs]
        Spotify[Spotify Web API\nFree Tier]
        Apple[Apple Music API\n*MOCKED* - Avoids $99/yr Fee]
        LLM[Gemini API\nFree Tier via AI Studio]
    end

    %% --- Connections & Data Flow ---
    
    %% User to Frontend
    User -->|Interacts| UI_Hybrid
    User -->|Logs in| UI_Auth
    User -->|Listens & Posts| UI_Player
    User -->|Browses| UI_Social

    %% Frontend to Backend Gateway
    UI_Auth -->|OAuth Tokens| API_Gateway
    UI_Hybrid -->|Prompt Payload| API_Gateway
    UI_Player -->|Playback State/ISRC| API_Gateway
    UI_Social -->|CRUD Requests| API_Gateway

    %% Gateway Routing
    API_Gateway -->|Auth Routes| Auth_Service
    API_Gateway -->|Generation Routes| AI_Orchestrator
    API_Gateway -->|Sync Routes| Sync_Service
    API_Gateway -->|Social Routes| Social_Service

    %% Backend Services to Database
    Auth_Service <-->|Read/Write User Data| DB_Users
    Social_Service <-->|Read/Write Posts| DB_Social
    Social_Service <-->|Save Playlists| DB_Playlists
    Sync_Service -->|Save Track IDs| DB_Playlists

    %% Backend to External APIs
    Auth_Service <-->|Verify Tokens| Spotify
    Auth_Service -.->|Verify Tokens| Apple
    
    AI_Orchestrator <-->|1. Parse Mood to Features| LLM
    AI_Orchestrator <-->|2. Fetch Tracks via Audio Features| Spotify
    
    Sync_Service -->|1. Fetch ISRC| Spotify
    Sync_Service -.->|2. Match ISRC| Apple
    
    %% Styling
    classDef frontend fill:#0ea5e9,stroke:#0284c7,stroke-width:2px,color:#fff;
    classDef backend fill:#10b981,stroke:#059669,stroke-width:2px,color:#fff;
    classDef database fill:#f59e0b,stroke:#d97706,stroke-width:2px,color:#fff;
    classDef external fill:#8b5cf6,stroke:#7c3aed,stroke-width:2px,color:#fff;
    classDef mocked fill:#ef4444,stroke:#b91c1c,stroke-width:2px,color:#fff,stroke-dasharray: 5 5;
    
    class Frontend,UI_Auth,UI_Hybrid,UI_Player,UI_Social frontend;
    class Backend,API_Gateway,Auth_Service,AI_Orchestrator,Sync_Service,Social_Service backend;
    class Database,DB_Users,DB_Playlists,DB_Social database;
    class External,Spotify,LLM external;
    class Apple mocked;
