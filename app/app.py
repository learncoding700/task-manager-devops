from flask import Flask, jsonify, request
import os
app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200

@app.route('/tasks', methods=['GET'])
def get_tasks():
    # Lazy import to avoid startup blocking
    import redis
    import psycopg2
    
    try:
        redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=6379,
            decode_responses=True,
            socket_connect_timeout=5
        )
        
        # Check cache first
        cached = redis_client.get('all_tasks')
        if cached:
            return jsonify({"source": "cache", "tasks": eval(cached)}), 200
        
        # If not in cache, get from database
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            database=os.getenv('POSTGRES_DB', 'tasks'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', 'postgres'),
            connect_timeout=5
        )
        cur = conn.cursor()
        cur.execute('SELECT id, title, completed FROM tasks')
        tasks = [{"id": row[0], "title": row[1], "completed": row[2]} for row in cur.fetchall()]
        cur.close()
        conn.close()
        
        # Store in cache for 60 seconds
        redis_client.setex('all_tasks', 60, str(tasks))
        
        return jsonify({"source": "database", "tasks": tasks}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/tasks', methods=['POST'])
def create_task():
    import redis
    import psycopg2
    
    try:
        redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=6379,
            decode_responses=True
        )
        
        data = request.get_json()
        title = data.get('title')
        
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            database=os.getenv('POSTGRES_DB', 'tasks'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', 'postgres')
        )
        cur = conn.cursor()
        cur.execute('INSERT INTO tasks (title, completed) VALUES (%s, %s) RETURNING id', (title, False))
        task_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        # Invalidate cache
        redis_client.delete('all_tasks')
        
        return jsonify({"id": task_id, "title": title, "completed": False}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
