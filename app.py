from flask import Flask, render_template_string, jsonify, request
import sqlite3
import datetime
import json

app = Flask(__name__)
DATABASE = 'monitoring.db'

def get_db_connection():
    """Create a database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def get_latest_metrics():
    """Get the most recent metrics from the database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM system_metrics 
        ORDER BY timestamp DESC 
        LIMIT 1
    ''')
    result = cursor.fetchone()
    conn.close()
    return result

def get_historical_metrics(hours=24):
    """Get historical metrics for charts"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT timestamp, cpu_percent, memory_percent, disk_percent, temperature
        FROM system_metrics 
        WHERE timestamp >= datetime('now', '-' || ? || ' hours')
        ORDER BY timestamp ASC
    ''', (hours,))
    results = cursor.fetchall()
    conn.close()
    return results

def get_recent_alerts(limit=10):
    """Get recent alerts"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM alerts 
        ORDER BY timestamp DESC 
        LIMIT ?
    ''', (limit,))
    results = cursor.fetchall()
    conn.close()
    return results

def format_bytes(bytes):
    """Convert bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024.0:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.2f} PB"

def format_uptime(seconds):
    """Format uptime seconds to readable string"""
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    return f"{days}d {hours}h {minutes}m"

# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Linux Monitor - Database View</title>
    <meta http-equiv="refresh" content="30">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: auto;
        }
        h1 {
            color: #333;
        }
        .dashboard {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .card {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .card h3 {
            margin-top: 0;
            color: #555;
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
        }
        .metric {
            margin: 15px 0;
        }
        .label {
            font-weight: bold;
            color: #666;
            display: inline-block;
            width: 120px;
        }
        .value {
            color: #4CAF50;
            font-weight: bold;
        }
        .progress-bar {
            width: 100%;
            height: 20px;
            background-color: #e0e0e0;
            border-radius: 10px;
            overflow: hidden;
            margin: 5px 0;
        }
        .progress-fill {
            height: 100%;
            background-color: #4CAF50;
            transition: width 0.3s ease;
        }
        .warning { background-color: #ff9800; }
        .critical { background-color: #f44336; }
        .alert {
            padding: 10px;
            margin: 5px 0;
            border-radius: 5px;
            border-left: 4px solid;
        }
        .alert-warning {
            background-color: #fff3e0;
            border-left-color: #ff9800;
        }
        .alert-critical {
            background-color: #ffebee;
            border-left-color: #f44336;
        }
        .timestamp {
            color: #999;
            font-size: 0.9em;
            margin-top: 10px;
        }
        .chart-container {
            margin-top: 30px;
            background: white;
            padding: 20px;
            border-radius: 10px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #4CAF50;
            color: white;
        }
        tr:hover {
            background-color: #f5f5f5;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Linux System Monitor (Database View)</h1>
        
        <div class="dashboard">
            <!-- Current Metrics Card -->
            <div class="card">
                <h3>Current System Status</h3>
                <div class="metric">
                    <span class="label">Hostname:</span>
                    <span class="value">{{ metrics.hostname }}</span>
                </div>
                <div class="metric">
                    <span class="label">Timestamp:</span>
                    <span class="value">{{ metrics.timestamp }}</span>
                </div>
                <div class="metric">
                    <span class="label">CPU Usage:</span>
                    <span class="value">{{ metrics.cpu_percent }}%</span>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {{ metrics.cpu_percent }}%"></div>
                    </div>
                </div>
                <div class="metric">
                    <span class="label">Memory Usage:</span>
                    <span class="value">{{ metrics.memory_percent }}%</span>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {{ metrics.memory_percent }}%"></div>
                    </div>
                    <small>Used: {{ memory_used }} / Total: {{ memory_total }}</small>
                </div>
                <div class="metric">
                    <span class="label">Disk Usage:</span>
                    <span class="value">{{ metrics.disk_percent }}%</span>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {{ metrics.disk_percent }}%"></div>
                    </div>
                    <small>Used: {{ disk_used }} / Total: {{ disk_total }}</small>
                </div>
                <div class="metric">
                    <span class="label">Temperature:</span>
                    <span class="value">{{ metrics.temperature }}°C</span>
                </div>
                <div class="metric">
                    <span class="label">Uptime:</span>
                    <span class="value">{{ uptime }}</span>
                </div>
                <div class="metric">
                    <span class="label">Processes:</span>
                    <span class="value">{{ metrics.process_count }}</span>
                </div>
            </div>

            <!-- Load Average Card -->
            <div class="card">
                <h3>Load Average</h3>
                <div class="metric">
                    <span class="label">1 minute:</span>
                    <span class="value">{{ metrics.load_average_1min }}</span>
                </div>
                <div class="metric">
                    <span class="label">5 minutes:</span>
                    <span class="value">{{ metrics.load_average_5min }}</span>
                </div>
                <div class="metric">
                    <span class="label">15 minutes:</span>
                    <span class="value">{{ metrics.load_average_15min }}</span>
                </div>
            </div>

            <!-- Recent Alerts Card -->
            <div class="card">
                <h3>Recent Alerts</h3>
                {% if alerts %}
                    {% for alert in alerts %}
                    <div class="alert alert-{{ alert.severity|lower }}">
                        <strong>{{ alert.severity }}</strong>: {{ alert.message }}<br>
                        <small>{{ alert.timestamp }}</small>
                    </div>
                    {% endfor %}
                {% else %}
                    <p>No recent alerts</p>
                {% endif %}
            </div>
        </div>

        <!-- Historical Charts -->
        <div class="chart-container">
            <h3>Historical Metrics (Last 24 Hours)</h3>
            <canvas id="metricsChart"></canvas>
        </div>

        <!-- Historical Data Table -->
        <div class="chart-container">
            <h3>Recent Data Points</h3>
            <table>
                <thead>
                    <tr>
                        <th>Timestamp</th>
                        <th>CPU %</th>
                        <th>Memory %</th>
                        <th>Disk %</th>
                        <th>Temperature</th>
                    </tr>
                </thead>
                <tbody>
                    {% for point in historical %}
                    <tr>
                        <td>{{ point.timestamp }}</td>
                        <td>{{ point.cpu_percent }}%</td>
                        <td>{{ point.memory_percent }}%</td>
                        <td>{{ point.disk_percent }}%</td>
                        <td>{{ point.temperature }}°C</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <div class="timestamp">
            Last updated: {{ current_time }} | Auto-refresh every 30 seconds
        </div>
    </div>

    <script>
        // Create historical chart
        const ctx = document.getElementById('metricsChart').getContext('2d');
        const chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: {{ chart_labels | safe }},
                datasets: [{
                    label: 'CPU %',
                    data: {{ chart_cpu | safe }},
                    borderColor: 'rgb(255, 99, 132)',
                    tension: 0.1
                }, {
                    label: 'Memory %',
                    data: {{ chart_memory | safe }},
                    borderColor: 'rgb(54, 162, 235)',
                    tension: 0.1
                }, {
                    label: 'Disk %',
                    data: {{ chart_disk | safe }},
                    borderColor: 'rgb(75, 192, 192)',
                    tension: 0.1
                }, {
                    label: 'Temperature °C',
                    data: {{ chart_temp | safe }},
                    borderColor: 'rgb(255, 159, 64)',
                    tension: 0.1,
                    yAxisID: 'y1'
                }]
            },
            options: {
                responsive: true,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                scales: {
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {
                            display: true,
                            text: 'Percentage %'
                        }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: {
                            display: true,
                            text: 'Temperature °C'
                        },
                        grid: {
                            drawOnChartArea: false,
                        },
                    }
                }
            }
        });
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    """Main dashboard page"""
    # Get latest metrics
    latest = get_latest_metrics()
    if not latest:
        return "No data in database. Please run setup_db.py first."
    
    # Get historical data
    historical = get_historical_metrics(24)
    
    # Get recent alerts
    alerts = get_recent_alerts(5)
    
    # Prepare chart data
    chart_labels = []
    chart_cpu = []
    chart_memory = []
    chart_disk = []
    chart_temp = []
    
    for row in historical[-50:]:  # Last 50 points for chart
        chart_labels.append(f"'{row['timestamp'][5:16]}'")
        chart_cpu.append(row['cpu_percent'])
        chart_memory.append(row['memory_percent'])
        chart_disk.append(row['disk_percent'])
        chart_temp.append(row['temperature'])
    
    return render_template_string(
        HTML_TEMPLATE,
        metrics=latest,
        memory_used=format_bytes(latest['memory_used']),
        memory_total=format_bytes(latest['memory_total']),
        disk_used=format_bytes(latest['disk_used']),
        disk_total=format_bytes(latest['disk_total']),
        uptime=format_uptime(latest['uptime_seconds']),
        alerts=alerts,
        historical=historical[-10:],  # Last 10 points for table
        chart_labels=','.join(chart_labels),
        chart_cpu=chart_cpu,
        chart_memory=chart_memory,
        chart_disk=chart_disk,
        chart_temp=chart_temp,
        current_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

@app.route('/api/metrics/latest')
def api_latest():
    """API endpoint for latest metrics"""
    metrics = get_latest_metrics()
    if metrics:
        return jsonify(dict(metrics))
    return jsonify({'error': 'No data found'}), 404

@app.route('/api/metrics/historical')
def api_historical():
    """API endpoint for historical metrics"""
    hours = request.args.get('hours', 24, type=int)
    metrics = get_historical_metrics(hours)
    return jsonify([dict(row) for row in metrics])

@app.route('/api/alerts')
def api_alerts():
    """API endpoint for alerts"""
    limit = request.args.get('limit', 10, type=int)
    alerts = get_recent_alerts(limit)
    return jsonify([dict(row) for row in alerts])

@app.route('/api/metrics/average')
def api_average():
    """API endpoint for average metrics over time period"""
    hours = request.args.get('hours', 1, type=int)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            AVG(cpu_percent) as avg_cpu,
            AVG(memory_percent) as avg_memory,
            AVG(disk_percent) as avg_disk,
            AVG(temperature) as avg_temp,
            MAX(timestamp) as period_end,
            MIN(timestamp) as period_start
        FROM system_metrics 
        WHERE timestamp >= datetime('now', '-' || ? || ' hours')
    ''', (hours,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return jsonify({
            'period_hours': hours,
            'avg_cpu': round(result['avg_cpu'], 2),
            'avg_memory': round(result['avg_memory'], 2),
            'avg_disk': round(result['avg_disk'], 2),
            'avg_temperature': round(result['avg_temp'], 2),
            'period_start': result['period_start'],
            'period_end': result['period_end']
        })
    return jsonify({'error': 'No data found'}), 404

if __name__ == '__main__':
    print("Starting Linux Monitor with Database Integration...")
    print("Make sure to run setup_db.py first to create and populate the database")
    print("Access the dashboard at: http://localhost:5000")
    print("API endpoints available at:")
    print("  - /api/metrics/latest")
    print("  - /api/metrics/historical")
    print("  - /api/alerts")
    print("  - /api/metrics/average")
    
    app.run(host='0.0.0.0', port=5000, debug=True)