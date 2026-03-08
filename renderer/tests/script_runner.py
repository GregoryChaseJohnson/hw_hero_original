import subprocess

def generate_report_from_script(script_name="/home/keithuncouth/red_pen_app/tests/sentence_parse2.py"):
    """
    Calls the given script and returns its output.
    """
    try:
        result = subprocess.run(
            ["python3", script_name], capture_output=True, text=True, check=True
        )
        return result.stdout
    except FileNotFoundError:
        print(f"Error: The script {script_name} was not found.")
        return ""
    except subprocess.CalledProcessError as e:
        print(f"Error running {script_name}: {e}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        return ""
