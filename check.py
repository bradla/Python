def check_real_server_status(ip_address):
    """Actual ping check"""
    try:
        response = subprocess.run(
            ['ping', '-c', '1', '-W', '2', ip_address],
            capture_output=True,
            timeout=5
        )
        if response.returncode == 0:
            # Parse response time from ping output
            return 'up', parse_response_time(response.stdout)
        return 'down', None
    except:
        return 'down', None

def check_real_ntp_drift(server_name):
    """Actual NTP drift check using ntpq or chronyc"""
    try:
        # For servers with ntpq
        result = subprocess.run(
            ['ntpq', '-c', 'rv'],
            capture_output=True,
            text=True,
            timeout=5
        )
        # Parse offset from output
        offset = parse_ntp_offset(result.stdout)
        return offset
    except:
        return None