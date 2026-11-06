import uvicorn
import sys
import os
import argparse
from app.tunnel import tunnel_manager

def main():
    parser = argparse.ArgumentParser(description="QuizBlizz Schul-Quiz Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host IP")
    parser.add_argument("--port", type=int, default=8000, help="Port")
    parser.add_argument("--no-tunnel", action="store_true", help="Deaktiviert Cloudflare Tunnel")
    args = parser.parse_args()

    tunnel_manager.port = args.port
    if not args.no_tunnel:
        tunnel_manager.start_tunnel()

    join_url = tunnel_manager.get_join_url()
    print("\n" + "="*65)
    print("⚡ QUIZBLIZZ - DAS BLITZSCHNELLE SCHUL-QUIZ")
    print("="*65)
    print(f"🖥️  BEAMER-ANSICHT (Host):   http://localhost:{args.port}/host")
    print(f"✏️  QUIZ-EDITOR:            http://localhost:{args.port}/editor")
    print(f"📱  SCHÜLER-LINK (iPads):    {join_url}/play")
    print("="*65 + "\n")

    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=False)

if __name__ == "__main__":
    main()
