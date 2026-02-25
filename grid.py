from flask import Flask, render_template_string, jsonify, request
import sqlite3
import datetime
import random
import subprocess
import socket
import time

app = Flask(__name__)
DATABASE = 'servers.db'

# HTML Template with Server Grid
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Server Monitoring Grid</title>
    <meta http-equiv="refresh" content="30">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f0f2f5;
        }
        .container {
            max-width: 1400px;
            margin: auto;
        }
        h1 {
            color: #1a237e;
            margin-bottom: 10px;
        }
        .subtitle {
            color: #666;
            margin-bottom: 30px;
        }
        .summary-stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            text-align: center;
        }
        .stat-value {
            font-size: 2em;
            font-weight: bold;
            color: #1a237e;
        }
        .stat-label {
            color: #666;
            margin-top: 5px;
        }
        .server-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .server-card {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }
        .server-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 5px 20px rgba(0,0,0,0.15);
        }
        .server-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e0e0e0;
        }
        .server-name {
            font-size: 1.2em;
            font-weight: bold;
            color: #1a237e;
        }
        .server-ip {
            color: #666;
            font-size: 0.9em;
        }
        .status-badge {
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 0.8em;
            font-weight: bold;
            text-transform: uppercase;
        }
        .status-up {
            background-color: #c8e6c9;
            color: #2e7d32;
        }
        .status-down {
            background-color: #ffcdd2;
            color: #c62828;
        }
        .status-warning {
            background-color: #fff3e0;
            color: #ef6c00;
        }
        .metric-row {
            display: flex;
            justify-content: space-between;
            margin: 10px 0;
            padding: 5px 0;
            border-bottom: 1px dashed #e0e0e0;
        }
        .metric-label {
            color: #666;
            font-size: 0.9em;
        }
        .metric-value {
            font-weight: bold;
        }
        .ntp-drift {
            font-family: monospace;
            font-size: 1.1em;
        }
        .drift-normal {
            color: #2e7d32;
        }
        .drift-warning {
            color: #ef6c00;
        }
        .drift-critical {
            color: #c62828;
        }
        .progress-bar {
            width: 100%;
            height: 8px;
            background-color: #e0e0e0;
            border-radius: 4px;
            overflow: hidden;
            margin: 5px 0;
        }
        .progress-fill {
            height: 100%;
            transition: width 0.3s ease;
        }
        .fill-good {
            background-color: #4caf50;
        }
        .fill-warning {
            background-color: #ff9800;
        }
        .fill-critical {
            background-color: #f44336;
        }
        .last-check {
            color: #999;
            font-size: 0.8em;
            text-align: right;
            margin-top: 10px;
        }
        .chart-container {
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-top: 30px;
        }
        .filter-bar {
            margin-bottom: 20px;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        .filter-btn {
            padding: 8px 16px;
            border: none;
            border-radius: 20px;
            cursor: pointer;
            background-color: white;
            color: #666;
            font-weight: bold;
            transition: all 0.2s;
        }
        .filter-btn.active {
            background-color: #1a237e;
            color: white;
        }
        .filter-btn:hover {
            background-color: #e0e0e0;
        }
        .refresh-indicator {
            color: #999;
            font-size: 0.9em;
            margin-top: 10px;
            text-align: right;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🌐 Server Monitoring Grid</h1>
        <div class="subtitle">Real-time server status with NTP drift monitoring</div>

        <!-- Summary Statistics -->
        <div class="summary-stats">
            <div class="stat-card">
                <div class="stat-value">{{ stats.total }}</div>
                <div class="stat-label">Total Servers</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: #2e7d32;">{{ stats.up }}</div>
                <div class="stat-label">Online</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: #c62828;">{{ stats.down }}</div>
                <div class="stat-label">Offline</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ stats.avg_drift }} ms</div>
                <div class="stat-label">Avg NTP Drift</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ stats.critical_drift }}</div>
                <div class="stat-label">Critical Drift</div>
            </div>
        </div>

        <!-- Filter Buttons -->
        <div class="filter-bar">
            <button class="filter-btn active" onclick="filterServers('all')">All Servers</button>
            <button class="filter-btn" onclick="filterServers('up')">Online</button>
            <button class="filter-btn" onclick="filterServers('down')">Offline</button>
            <button class="filter-btn" onclick="filterServers('drift-warning')">NTP Warning</button>
            <button class="filter-btn" onclick="filterServers('drift-critical')">NTP Critical</button>
        </div>

        <!-- Server Grid -->
        <div class="server-grid" id="serverGrid">
            {% for server in servers %}
            <div class="server-card" data-status="{{ 'up' if server.status == 'up' else 'down' }}" 
                 data-drift="{{ 'critical' if server.ntp_drift|abs > 100 else 'warning' if server.ntp_drift|abs > 50 else 'normal' }}">
                <div class="server-header">
                    <div>
                        <div class="server-name">{{ server.name }}</div>
                        <div class="server-ip">{{ server.ip_address }}</div>
                    </div>
                    <span class="status-badge status-{{ server.status }}">
                        {{ server.status }}
                    </span>
                </div>

                <!-- NTP Drift -->
                <div class="metric-row">
                    <span class="metric-label">⏰ NTP Drift:</span>
                    <span class="metric-value ntp-drift 
                        {% if server.ntp_drift|abs > 100 %}drift-critical
                        {% elif server.ntp_drift|abs > 50 %}drift-warning
                        {% else %}drift-normal{% endif %}">
                        {{ "%.2f"|format(server.ntp_drift) }} ms
                    </span>
                </div>

                <!-- Response Time -->
                <div class="metric-row">
                    <span class="metric-label">📡 Response Time:</span>
                    <span class="metric-value">{{ "%.2f"|format(server.response_time) }} ms</span>
                </div>

                <!-- CPU Usage -->
                <div class="metric-row">
                    <span class="metric-label">💻 CPU Usage:</span>
                    <span class="metric-value">{{ server.cpu_usage }}%</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill {% if server.cpu_usage > 80 %}fill-critical{% elif server.cpu_usage > 60 %}fill-warning{% else %}fill-good{% endif %}" 
                         style="width: {{ server.cpu_usage }}%"></div>
                </div>

                <!-- Memory Usage -->
                <div class="metric-row">
                    <span class="metric-label">📊 Memory Usage:</span>
                    <span class="metric-value">{{ server.memory_usage }}%</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill {% if server.memory_usage > 80 %}fill-critical{% elif server.memory_usage > 60 %}fill-warning{% else %}fill-good{% endif %}" 
                         style="width: {{ server.memory_usage }}%"></div>
                </div>

                <!-- Last Sync -->
                <div class="metric-row">
                    <span class="metric-label">🕒 Last NTP Sync:</span>
                    <span class="metric-value">{{ server.last_ntp_sync }}</span>
                </div>

                <!-- Additional Info -->
                <div class="metric-row">
                    <span class="metric-label">📦 Services:</span>
                    <span class="metric-value">{{ server.services_running }}/{{ server.services_total }}</span>
                </div>

                <div class="last-check">
                    Last check: {{ server.last_check }}
                </div>
            </div>
            {% endfor %}
        </div>

        <!-- NTP Drift Chart -->
        <div class="chart-container">
            <h3>📈 NTP Drift Trends (Last 24 Hours)</h3>
            <canvas id="ntpDriftChart"></canvas>
        </div>

        <div class="refresh-indicator">
            Auto-refresh every 30 seconds | Last updated: {{ current_time }}
        </div>
    </div>

    <script>
        // Filter servers based on status or drift
        function filterServers(filter) {
            const cards = document.querySelectorAll('.server-card');
            const buttons = document.querySelectorAll('.filter-btn');
            
            buttons.forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            
            cards.forEach(card => {
                switch(filter) {
                    case 'all':
                        card.style.display = 'block';
                        break;
                    case 'up':
                        card.style.display = card.dataset.status === 'up' ? 'block' : 'none';
                        break;
                    case 'down':
                        card.style.display = card.dataset.status === 'down' ? 'block' : 'none';
                        break;
                    case 'drift-warning':
                        card.style.display = card.dataset.drift === 'warning' ? 'block' : 'none';
                        break;
                    case 'drift-critical':
                        card.style.display = card.dataset.drift === 'critical' ? 'block' : 'none';
                        break;
                }
            });
        }

        // NTP Drift Chart
        const ctx = document.getElementById('ntpDriftChart').getContext('2d');
        const chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: {{ chart_labels | safe }},
                datasets: [
                    {% for server in servers[:5] %}
                    {
                        label: '{{ server.name }}',
                        data: {{ server.drift_history | safe }},
                        borderColor: 'hsl({{ loop.index * 60 }}, 70%, 50%)',
                        tension: 0.1
                    },
                    {% endfor %}
                ]
            },
            options: {
                responsive: true,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                scales: {
                    y: {
                        title: {
                            display: true,
                            text: 'NTP Drift (ms)'
                        }
                    }
                }
            }
        });
    </script>
</body>
</html>
'''

def init_database():
    """Initialize the database with server information"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Create servers table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS servers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            ip_address TEXT,
            location TEXT,
            environment TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create monitoring data table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS server_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            server_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT,
            response_time REAL,
            ntp_drift REAL,
            cpu_usage REAL,
            memory_usage REAL,
            disk_usage REAL,
            services_running INTEGER,
            services_total INTEGER,
            last_ntp_sync DATETIME,
            FOREIGN KEY (server_id) REFERENCES servers (id)
        )
    ''')
    
    # Insert sample servers if table is empty
    cursor.execute("SELECT COUNT(*) FROM servers")
    if cursor.fetchone()[0] == 0:
        sample_servers = [
            ('web-server-01', '192.168.1.10', 'US-East', 'production'),
            ('web-server-02', '192.168.1.11', 'US-East', 'production'),
            ('db-server-01', '192.168.1.20', 'US-East', 'production'),
            ('db-server-02', '192.168.1.21', 'US-West', 'production'),
            ('cache-server-01', '192.168.1.30', 'US-East', 'staging'),
            ('app-server-01', '192.168.1.40', 'EU-West', 'production'),
            ('app-server-02', '192.168.1.41', 'EU-West', 'production'),
            ('monitoring-server', '192.168.1.50', 'US-East', 'management'),
            ('backup-server', '192.168.1.60', 'US-West', 'backup'),
            ('dns-server-01', '192.168.1.70', 'AP-Southeast', 'production'),
        ]
        
        for server in sample_servers:
            cursor.execute('''
                INSERT INTO servers (name, ip_address, location, environment)
                VALUES (?, ?, ?, ?)
            ''', server)
    
    conn.commit()
    conn.close()

def get_db_connection():
    """Create a database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def simulate_ntp_drift():
    """Simulate NTP drift with realistic patterns"""
    # Some servers have stable drift, others fluctuate
    base_drift = random.uniform(-150, 150)
    
    # Add some random variation
    variation = random.uniform(-20, 20)
    
    # Occasionally simulate large drift (NTP issues)
    if random.random() < 0.05:  # 5% chance
        base_drift += random.uniform(-500, 500)
    
    return round(base_drift + variation, 2)

def check_server_status(ip_address):
    """Simulate checking server status (in real app, this would use ICMP/SSH)"""
    # Simulate network conditions
    if random.random() < 0.9:  # 90% uptime
        status = 'up'
        response_time = random.uniform(5, 150)
    else:
        status = 'down'
        response_time = None
    
    return status, response_time

def generate_server_metrics():
    """Generate current metrics for all servers"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all servers
    cursor.execute("SELECT * FROM servers")
    servers = cursor.fetchall()
    
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    server_data = []
    
    for server in servers:
        # Check server status
        status, response_time = check_server_status(server['ip_address'])
        
        # Generate NTP drift
        ntp_drift = simulate_ntp_drift() if status == 'up' else None
        
        # Generate other metrics
        if status == 'up':
            cpu = random.randint(10, 95)
            memory = random.randint(20, 90)
            disk = random.randint(30, 85)
            services_running = random.randint(8, 12)
            services_total = 12
            last_sync = (datetime.datetime.now() - datetime.timedelta(
                minutes=random.randint(0, 60))).strftime("%H:%M:%S")
        else:
            cpu = memory = disk = 0
            services_running = 0
            services_total = 12
            last_sync = 'N/A'
            response_time = 0
        
        # Insert metrics into database
        cursor.execute('''
            INSERT INTO server_metrics 
            (server_id, status, response_time, ntp_drift, cpu_usage, 
             memory_usage, disk_usage, services_running, services_total, last_ntp_sync)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            server['id'], status, response_time, ntp_drift, cpu, memory, disk,
            services_running, services_total, 
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") if status == 'up' else None
        ))
        
        # Get last 24 hours of NTP drift for chart
        cursor.execute('''
            SELECT timestamp, ntp_drift FROM server_metrics 
            WHERE server_id = ? AND timestamp >= datetime('now', '-24 hours')
            AND ntp_drift IS NOT NULL
            ORDER BY timestamp ASC
        ''', (server['id'],))
        
        drift_history = cursor.fetchall()
        drift_values = [row['ntp_drift'] for row in drift_history]
        drift_timestamps = [row['timestamp'][11:16] for row in drift_history[-20:]]  # Last 20 points
        
        server_data.append({
            'id': server['id'],
            'name': server['name'],
            'ip_address': server['ip_address'],
            'location': server['location'],
            'environment': server['environment'],
            'status': status,
            'response_time': response_time if response_time else 0,
            'ntp_drift': ntp_drift if ntp_drift else 0,
            'cpu_usage': cpu,
            'memory_usage': memory,
            'disk_usage': disk,
            'services_running': services_running,
            'services_total': services_total,
            'last_ntp_sync': last_sync,
            'last_check': current_time,
            'drift_history': drift_values[-20:] if drift_values else [0] * 20,
            'drift_timestamps': drift_timestamps
        })
    
    conn.commit()
    conn.close()
    return server_data

def calculate_summary_stats(servers):
    """Calculate summary statistics"""
    total = len(servers)
    up = sum(1 for s in servers if s['status'] == 'up')
    down = total - up
    
    # Calculate average NTP drift (only for up servers)
    drifts = [s['ntp_drift'] for s in servers if s['status'] == 'up' and s['ntp_drift'] is not None]
    avg_drift = round(sum(drifts) / len(drifts), 2) if drifts else 0
    
    # Count servers with critical drift (>100ms)
    critical_drift = sum(1 for s in servers if s['status'] == 'up' and abs(s['ntp_drift']) > 100)
    
    return {
        'total': total,
        'up': up,
        'down': down,
        'avg_drift': avg_drift,
        'critical_drift': critical_drift
    }

@app.route('/')
def index():
    """Main dashboard with server grid"""
    # Generate fresh metrics
    servers = generate_server_metrics()
    stats = calculate_summary_stats(servers)
    
    # Prepare chart data
    chart_labels = []
    chart_datasets = []
    
    # Get NTP drift history for top 5 servers
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get timestamps for last 24 hours
    cursor.execute('''
        SELECT DISTINCT strftime('%H:%M', timestamp) as hour
        FROM server_metrics 
        WHERE timestamp >= datetime('now', '-24 hours')
        GROUP BY hour
        ORDER BY timestamp ASC
        LIMIT 24
    ''')
    chart_labels = [row['hour'] for row in cursor.fetchall()]
    
    conn.close()
    
    return render_template_string(
        HTML_TEMPLATE,
        servers=servers,
        stats=stats,
        chart_labels=chart_labels,
        current_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

@app.route('/api/servers')
def api_servers():
    """API endpoint for current server status"""
    servers = generate_server_metrics()
    return jsonify({
        'timestamp': datetime.datetime.now().isoformat(),
        'servers': servers
    })

@app.route('/api/servers/<server_name>')
def api_server_detail(server_name):
    """API endpoint for specific server details"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT s.*, m.* 
        FROM servers s
        LEFT JOIN server_metrics m ON s.id = m.server_id
        WHERE s.name = ?
        ORDER BY m.timestamp DESC
        LIMIT 1
    ''', (server_name,))
    
    server = cursor.fetchone()
    conn.close()
    
    if server:
        return jsonify(dict(server))
    return jsonify({'error': 'Server not found'}), 404

@app.route('/api/ntp-drift/history')
def api_ntp_history():
    """API endpoint for NTP drift history"""
    hours = request.args.get('hours', 24, type=int)
    server_id = request.args.get('server_id', None, type=int)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if server_id:
        cursor.execute('''
            SELECT timestamp, ntp_drift, server_id
            FROM server_metrics 
            WHERE server_id = ? AND ntp_drift IS NOT NULL
            AND timestamp >= datetime('now', '-' || ? || ' hours')
            ORDER BY timestamp ASC
        ''', (server_id, hours))
    else:
        cursor.execute('''
            SELECT timestamp, ntp_drift, server_id
            FROM server_metrics 
            WHERE ntp_drift IS NOT NULL
            AND timestamp >= datetime('now', '-' || ? || ' hours')
            ORDER BY timestamp ASC
        ''', (hours,))
    
    results = cursor.fetchall()
    conn.close()
    
    return jsonify([dict(row) for row in results])

@app.route('/api/summary')
def api_summary():
    """API endpoint for summary statistics"""
    servers = generate_server_metrics()
    stats = calculate_summary_stats(servers)
    return jsonify(stats)

@app.route('/api/check-ntp/<server_name>', methods=['POST'])
def check_ntp(server_name):
    """Manually trigger NTP check for a server"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM servers WHERE name = ?", (server_name,))
    server = cursor.fetchone()
    
    if not server:
        return jsonify({'error': 'Server not found'}), 404
    
    # Simulate NTP check
    ntp_drift = simulate_ntp_drift()
    status = 'up' if random.random() < 0.95 else 'down'
    
    # Insert check result
    cursor.execute('''
        INSERT INTO server_metrics 
        (server_id, status, ntp_drift, last_ntp_sync, timestamp)
        VALUES (?, ?, ?, ?, ?)
    ''', (server['id'], status, ntp_drift, datetime.datetime.now(), datetime.datetime.now()))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'server': server_name,
        'ntp_drift': ntp_drift,
        'status': status,
        'timestamp': datetime.datetime.now().isoformat()
    })

if __name__ == '__main__':
    # Initialize database
    init_database()
    
    print("🚀 Starting Server Monitoring Grid...")
    print("📊 Access the dashboard at: http://localhost:5000")
    print("\n📡 API Endpoints:")
    print("  - GET  /api/servers              - List all servers with current status")
    print("  - GET  /api/servers/<name>       - Get specific server details")
    print("  - GET  /api/ntp-drift/history    - NTP drift history")
    print("  - GET  /api/summary               - Summary statistics")
    print("  - POST /api/check-ntp/<name>      - Trigger NTP check")
    
    app.run(host='0.0.0.0', port=5000, debug=True)