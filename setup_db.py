import sqlite3
import random
import datetime
import time

def init_database():
    """Initialize the database and create tables"""
    conn = sqlite3.connect('monitoring.db')
    cursor = conn.cursor()
    
    # Create system metrics table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            hostname TEXT,
            cpu_percent REAL,
            memory_percent REAL,
            memory_used INTEGER,
            memory_total INTEGER,
            disk_percent REAL,
            disk_used INTEGER,
            disk_total INTEGER,
            process_count INTEGER,
            uptime_seconds INTEGER,
            temperature REAL,
            load_average_1min REAL,
            load_average_5min REAL,
            load_average_15min REAL
        )
    ''')
    
    # Create alerts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            severity TEXT,
            metric TEXT,
            value REAL,
            threshold REAL,
            message TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

def generate_sample_data():
    """Generate sample monitoring data"""
    hostname = "linux-server-01"
    
    # Generate realistic looking metrics with some variation
    cpu = random.uniform(10, 60)
    memory = random.uniform(20, 70)
    disk = random.uniform(30, 80)
    processes = random.randint(80, 150)
    temp = random.uniform(35, 65)
    load1 = random.uniform(0.5, 4.0)
    load5 = random.uniform(0.5, 3.5)
    load15 = random.uniform(0.5, 3.0)
    
    # Occasionally spike CPU or memory
    if random.random() < 0.1:  # 10% chance of spike
        cpu = random.uniform(80, 95)
        # Create an alert for high CPU
        create_alert('WARNING', 'cpu_percent', cpu, 80, f"High CPU usage detected: {cpu:.1f}%")
    
    if random.random() < 0.05:  # 5% chance of high memory
        memory = random.uniform(85, 95)
        create_alert('CRITICAL', 'memory_percent', memory, 90, f"Critical memory usage: {memory:.1f}%")
    
    return {
        'hostname': hostname,
        'cpu_percent': round(cpu, 1),
        'memory_percent': round(memory, 1),
        'memory_used': int(memory * 1024 * 1024 * 16),  # Simulate 16GB total
        'memory_total': 16 * 1024 * 1024 * 1024,  # 16GB in bytes
        'disk_percent': round(disk, 1),
        'disk_used': int(disk * 1024 * 1024 * 500),  # 500GB disk
        'disk_total': 500 * 1024 * 1024 * 1024,  # 500GB in bytes
        'process_count': processes,
        'uptime_seconds': random.randint(86400, 604800),  # 1-7 days in seconds
        'temperature': round(temp, 1),
        'load_average_1min': round(load1, 2),
        'load_average_5min': round(load5, 2),
        'load_average_15min': round(load15, 2)
    }

def create_alert(severity, metric, value, threshold, message):
    """Insert an alert into the database"""
    conn = sqlite3.connect('monitoring.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO alerts (severity, metric, value, threshold, message)
        VALUES (?, ?, ?, ?, ?)
    ''', (severity, metric, value, threshold, message))
    conn.commit()
    conn.close()

def insert_metrics(metrics):
    """Insert metrics into the database"""
    conn = sqlite3.connect('monitoring.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO system_metrics (
            hostname, cpu_percent, memory_percent, memory_used, memory_total,
            disk_percent, disk_used, disk_total, process_count, uptime_seconds,
            temperature, load_average_1min, load_average_5min, load_average_15min
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        metrics['hostname'], metrics['cpu_percent'], metrics['memory_percent'],
        metrics['memory_used'], metrics['memory_total'], metrics['disk_percent'],
        metrics['disk_used'], metrics['disk_total'], metrics['process_count'],
        metrics['uptime_seconds'], metrics['temperature'], metrics['load_average_1min'],
        metrics['load_average_5min'], metrics['load_average_15min']
    ))
    
    conn.commit()
    conn.close()

def populate_data(duration_minutes=5, interval_seconds=30):
    """Populate the database with sample data over a time period"""
    print(f"Populating database with {duration_minutes} minutes of data at {interval_seconds}s intervals...")
    
    end_time = datetime.datetime.now() + datetime.timedelta(minutes=duration_minutes)
    
    while datetime.datetime.now() < end_time:
        metrics = generate_sample_data()
        insert_metrics(metrics)
        
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Inserted metrics: CPU={metrics['cpu_percent']}%, "
              f"Memory={metrics['memory_percent']}%, Disk={metrics['disk_percent']}%")
        
        time.sleep(interval_seconds)
    
    print("Data population complete!")

if __name__ == "__main__":
    # Initialize the database
    init_database()
    
    # Populate with some initial historical data
    print("Generating historical data...")
    for i in range(20):  # Generate 20 data points with timestamps in the past
        metrics = generate_sample_data()
        # Adjust timestamp to be in the past
        past_time = datetime.datetime.now() - datetime.timedelta(minutes=(20-i)*5)
        conn = sqlite3.connect('monitoring.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO system_metrics (
                timestamp, hostname, cpu_percent, memory_percent, memory_used, memory_total,
                disk_percent, disk_used, disk_total, process_count, uptime_seconds,
                temperature, load_average_1min, load_average_5min, load_average_15min
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            past_time, metrics['hostname'], metrics['cpu_percent'], metrics['memory_percent'],
            metrics['memory_used'], metrics['memory_total'], metrics['disk_percent'],
            metrics['disk_used'], metrics['disk_total'], metrics['process_count'],
            metrics['uptime_seconds'], metrics['temperature'], metrics['load_average_1min'],
            metrics['load_average_5min'], metrics['load_average_15min']
        ))
        conn.commit()
        conn.close()
    
    print("Starting real-time data population...")
    # Then start real-time data population
    populate_data(duration_minutes=30, interval_seconds=10)