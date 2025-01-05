# Polling System

A real-time polling system built with Flask and Flask-SocketIO, enabling dynamic interaction with polls and votes. This project supports creating, staging, publishing, and archiving polls, while allowing participants to cast votes in an interactive and real-time environment.

## Features

- **Real-Time Voting:** Updates the voting results dynamically for all connected clients.
- **Poll Management:** Create, stage, publish, archive, and delete polls.
- **Vote Tracking:** Captures voter details and timestamps.
- **Database Integration:** Uses SQLite for managing polls, options, and votes.
- **Dockerized Deployment:** Easily deployable using Docker and Docker Compose.

## Requirements

- Python 3.9 or later
- Docker (optional for containerized deployment)

### Python Dependencies

The project uses the following dependencies:

- Flask
- Flask-SocketIO
- Eventlet
- Werkzeug
- Python-SocketIO
- dnspython

Refer to the `requirements.txt` for the full list.

## Getting Started

### Clone the Repository

```bash
git clone https://github.com/bel52/polling.git
cd polling
