from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import sqlite3
import os
import json

# Initialize Flask App
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

# Database setup
def init_db():
    if not os.path.exists('poll.db'):
        conn = sqlite3.connect('poll.db')
        c = conn.cursor()
        # Create questions table
        c.execute('''CREATE TABLE questions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        question TEXT NOT NULL
                    )''')
        # Create options table
        c.execute('''CREATE TABLE options (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        question_id INTEGER NOT NULL,
                        option TEXT NOT NULL,
                        votes INTEGER DEFAULT 0
                    )''')
        # Create archived_polls table
        c.execute('''CREATE TABLE archived_polls (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        question TEXT NOT NULL,
                        options TEXT NOT NULL -- JSON string of options and votes
                    )''')
        # Create staged_polls table
        c.execute('''CREATE TABLE staged_polls (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        question TEXT NOT NULL,
                        options TEXT NOT NULL -- JSON string of options
                    )''')
        # Create votes table
        c.execute('''CREATE TABLE IF NOT EXISTS votes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        option_id INTEGER NOT NULL,
                        student_name TEXT NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(option_id) REFERENCES options(id)
                    )''')
        conn.commit()
        conn.close()
    else:
        conn = sqlite3.connect('poll.db')
        c = conn.cursor()
        # Check if the votes table exists, and create it if it doesn't
        c.execute('''CREATE TABLE IF NOT EXISTS votes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        option_id INTEGER NOT NULL,
                        student_name TEXT NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(option_id) REFERENCES options(id)
                    )''')
        conn.commit()
        conn.close()

# Initialize database
init_db()

@app.route('/init_db', methods=['GET'])
def initialize_db():
    init_db()
    return jsonify({"success": True}), 200

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/professor')
def professor():
    return render_template('professor.html')

@app.route('/create_poll', methods=['POST'])
def create_poll():
    data = request.json
    question = data.get('question')
    options = data.get('options')

    if not question or not options:
        return jsonify({"error": "Invalid input"}), 400

    conn = sqlite3.connect('poll.db')
    c = conn.cursor()

    # Archive the current poll
    c.execute("SELECT * FROM questions ORDER BY id DESC LIMIT 1")
    current_poll = c.fetchone()
    if current_poll:
        # Get options and votes for the current poll
        c.execute("SELECT option, votes FROM options WHERE question_id = ?", (current_poll[0],))
        current_options = [{"option": row[0], "votes": row[1]} for row in c.fetchall()]
        # Archive the poll
        c.execute("INSERT INTO archived_polls (question, options) VALUES (?, ?)", 
                  (current_poll[1], json.dumps(current_options)))
        # Remove the current poll
        c.execute("DELETE FROM questions WHERE id = ?", (current_poll[0],))
        c.execute("DELETE FROM options WHERE question_id = ?", (current_poll[0],))

    # Create the new poll
    c.execute("INSERT INTO questions (question) VALUES (?)", (question,))
    question_id = c.lastrowid
    for option in options:
        c.execute("INSERT INTO options (question_id, option) VALUES (?, ?)", (question_id, option))

    conn.commit()
    conn.close()

    # Notify clients of the new poll
    socketio.emit('new_poll', {"question": question, "options": options, "id": question_id})

    return jsonify({"success": True}), 200

@app.route('/votes_with_names', methods=['GET'])
def votes_with_names():
    try:
        conn = sqlite3.connect('poll.db')
        c = conn.cursor()
        c.execute("""
            SELECT v.student_name, o.option, v.timestamp
            FROM votes v
            JOIN options o ON v.option_id = o.id
            ORDER BY v.timestamp DESC
        """)
        votes = [{"student_name": row[0], "option": row[1], "timestamp": row[2]} for row in c.fetchall()]
        conn.close()
        return jsonify(votes), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/vote', methods=['POST'])
def vote():
    data = request.json
    option_id = data.get('option_id')
    student_name = data.get('student_name')

    if not student_name:
        return jsonify({"error": "Student name is required"}), 400

    try:
        conn = sqlite3.connect('poll.db')
        c = conn.cursor()

        # Validate that the option belongs to the current poll
        c.execute("""
            SELECT questions.id FROM questions
            JOIN options ON questions.id = options.question_id
            WHERE options.id = ?
        """, (option_id,))
        current_poll_id = c.fetchone()

        # Get the current active poll ID
        c.execute("SELECT id FROM questions ORDER BY id DESC LIMIT 1")
        active_poll_id = c.fetchone()

        if not current_poll_id or not active_poll_id or current_poll_id[0] != active_poll_id[0]:
            conn.close()
            return jsonify({
                "error": "Stale poll. You are voting on an old poll. The page will refresh to show the current poll."
            }), 400

        # Increment vote count
        c.execute("UPDATE options SET votes = votes + 1 WHERE id = ?", (option_id,))

        # Store the student's vote
        c.execute("INSERT INTO votes (option_id, student_name) VALUES (?, ?)", (option_id, student_name))

        # Fetch updated results
        c.execute("""
            SELECT id, option, votes 
            FROM options 
            WHERE question_id = (SELECT question_id FROM options WHERE id = ?)
        """, (option_id,))
        results = [{"id": row[0], "option": row[1], "votes": row[2]} for row in c.fetchall()]

        conn.commit()
        conn.close()

        # Emit the results to all clients, including the voter's name
        socketio.emit('update_results', {"results": results, "voter": student_name})

        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/current_poll', methods=['GET'])
def current_poll():
    conn = sqlite3.connect('poll.db')
    c = conn.cursor()
    c.execute("SELECT * FROM questions ORDER BY id DESC LIMIT 1")
    question = c.fetchone()

    if question:
        c.execute("SELECT id, option, votes FROM options WHERE question_id = ?", (question[0],))
        options = [{"id": row[0], "option": row[1], "votes": row[2]} for row in c.fetchall()]
        conn.close()
        return jsonify({"id": question[0], "question": question[1], "options": options}), 200
    else:
        conn.close()
        return jsonify({"message": "No active poll"}), 404

@app.route('/archived_polls', methods=['GET'])
def get_archived_polls():
    try:
        conn = sqlite3.connect('poll.db')
        c = conn.cursor()
        c.execute("SELECT id, question, options FROM archived_polls")
        archived_polls = [{"id": row[0], "question": row[1], "options": row[2]} for row in c.fetchall()]
        conn.close()
        return jsonify(archived_polls), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/delete_poll/<int:poll_id>', methods=['DELETE'])
def delete_poll(poll_id):
    try:
        print(f"Received request to delete poll with ID: {poll_id}")
        conn = sqlite3.connect('poll.db')
        c = conn.cursor()
        # Delete the archived poll
        c.execute("DELETE FROM archived_polls WHERE id = ?", (poll_id,))
        conn.commit()
        conn.close()
        print(f"Successfully deleted poll with ID: {poll_id}")
        return jsonify({"success": True}), 200
    except Exception as e:
        print(f"Error deleting poll: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/stage_poll', methods=['POST'])
def create_staged_poll():
    """Create a staged poll."""
    data = request.json
    question = data.get('question')
    options = data.get('options')

    if not question or not options:
        return jsonify({"error": "Invalid input"}), 400

    try:
        conn = sqlite3.connect('poll.db')
        c = conn.cursor()
        c.execute("INSERT INTO staged_polls (question, options) VALUES (?, ?)", 
                  (question, json.dumps(options)))
        conn.commit()
        print(f"Staged Poll Added: {question}, {options}")  # Debugging statement
        conn.close()
        return jsonify({"success": True}), 200
    except Exception as e:
        print(f"Error staging poll: {e}")  # Debugging statement
        return jsonify({"error": str(e)}), 500

@app.route('/staged_polls', methods=['GET'])
def get_staged_polls():
    """Fetch all staged polls."""
    try:
        conn = sqlite3.connect('poll.db')
        c = conn.cursor()
        c.execute("SELECT id, question, options FROM staged_polls")
        rows = c.fetchall()  # Fetch rows
        print("Fetched Rows:", rows)  # Debugging statement
        staged_polls = [{"id": row[0], "question": row[1], "options": row[2]} for row in rows]
        conn.close()
        return jsonify(staged_polls), 200
    except Exception as e:
        print("Error fetching staged polls:", e)  # Debugging statement
        return jsonify({"error": str(e)}), 500

@app.route('/publish_staged_poll/<int:poll_id>', methods=['POST'])
def publish_staged_poll(poll_id):
    """Publish a staged poll."""
    try:
        conn = sqlite3.connect('poll.db')
        c = conn.cursor()

        # Archive the current active poll
        c.execute("SELECT * FROM questions ORDER BY id DESC LIMIT 1")
        current_poll = c.fetchone()
        if current_poll:
            # Get options and votes for the current poll
            c.execute("SELECT option, votes FROM options WHERE question_id = ?", (current_poll[0],))
            current_options = [{"option": row[0], "votes": row[1]} for row in c.fetchall()]
            # Archive the poll
            c.execute("INSERT INTO archived_polls (question, options) VALUES (?, ?)",
                      (current_poll[1], json.dumps(current_options)))
            # Remove the current poll
            c.execute("DELETE FROM questions WHERE id = ?", (current_poll[0],))
            c.execute("DELETE FROM options WHERE question_id = ?", (current_poll[0],))

        # Fetch the staged poll
        c.execute("SELECT question, options FROM staged_polls WHERE id = ?", (poll_id,))
        poll = c.fetchone()
        if not poll:
            return jsonify({"error": "Poll not found"}), 404

        question, options = poll[0], json.loads(poll[1])

        # Publish the staged poll as active
        c.execute("INSERT INTO questions (question) VALUES (?)", (question,))
        question_id = c.lastrowid
        for option in options:
            c.execute("INSERT INTO options (question_id, option) VALUES (?, ?)", (question_id, option))

        # Remove the staged poll
        c.execute("DELETE FROM staged_polls WHERE id = ?", (poll_id,))

        conn.commit()
        conn.close()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/edit_staged_poll/<int:poll_id>', methods=['PUT'])
def edit_staged_poll(poll_id):
    """Edit a staged poll."""
    data = request.json
    question = data.get('question')
    options = data.get('options')

    if not question or not options:
        return jsonify({"error": "Invalid input"}), 400

    try:
        conn = sqlite3.connect('poll.db')
        c = conn.cursor()
        c.execute("UPDATE staged_polls SET question = ?, options = ? WHERE id = ?", 
                  (question, json.dumps(options), poll_id))
        conn.commit()
        conn.close()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/delete_staged_poll/<int:poll_id>', methods=['DELETE'])
def delete_staged_poll(poll_id):
    """Delete a staged poll."""
    try:
        conn = sqlite3.connect('poll.db')
        c = conn.cursor()

        # Check if the poll exists
        c.execute("SELECT COUNT(*) FROM staged_polls WHERE id = ?", (poll_id,))
        if c.fetchone()[0] == 0:
            conn.close()
            return jsonify({"error": "Poll not found"}), 404

        # Delete the poll
        c.execute("DELETE FROM staged_polls WHERE id = ?", (poll_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Make sure to use `socketio.run` instead of `app.run`
    socketio.run(app, host='0.0.0.0', port=5000)

@app.route('/clear_poll', methods=['POST'])
def clear_poll():
    try:
        conn = sqlite3.connect('poll.db')
        c = conn.cursor()

        # Archive the current poll
        c.execute("SELECT * FROM questions ORDER BY id DESC LIMIT 1")
        current_poll = c.fetchone()
        if current_poll:
            # Get options and votes for the current poll
            c.execute("SELECT option, votes FROM options WHERE question_id = ?", (current_poll[0],))
            current_options = [{"option": row[0], "votes": row[1]} for row in c.fetchall()]
            # Archive the poll
            c.execute("INSERT INTO archived_polls (question, options) VALUES (?, ?)", 
                      (current_poll[1], json.dumps(current_options)))
            # Remove the current poll
            c.execute("DELETE FROM questions WHERE id = ?", (current_poll[0],))
            c.execute("DELETE FROM options WHERE question_id = ?", (current_poll[0],))

        conn.commit()
        conn.close()

        # Emit an event to notify clients that the poll has been cleared
        socketio.emit('update_results', {"results": [], "voter": None})

        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
