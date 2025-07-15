import subprocess
import os
import sys

# --- Configuration ---
# Set the number of times you want the entire workflow to run
NUM_RUNS = 5

# Set the relative path to the directory containing the scripts
PROCESS_DIR = "src/cyberdata/process"

# Define the sequence of commands to run for one workflow cycle.
# Commands with arguments are represented as a list of strings.
WORKFLOW_STEPS = [
    ["python", "problems.py"],
    ["python", "extend_problems.py"],
    ["python", "small_dataset.py"],
    ["python", "validate_small.py"],
    # ["python", "generator.py", "--count", "50"],
    ["python", "generator.py"], # going with default count as we have limited resources. We can't have large token size while training model later.
    ["python", "validate_large.py"],
]

def run_single_workflow(run_number: int):
    """
    Executes one full cycle of the data generation workflow.

    Args:
        run_number: The current iteration number, for logging.

    Returns:
        True if the workflow completed successfully, False otherwise.
    """
    for i, command in enumerate(WORKFLOW_STEPS):
        step_num = i + 1
        command_str = " ".join(command)
        print(f"[RUN {run_number}/STEP {step_num}] Executing: {command_str}")

        try:
            # Execute the command.
            # `cwd` runs the command from within the specified directory.
            # `check=True` raises a CalledProcessError if the command returns a non-zero exit code.
            # `capture_output=True` and `text=True` capture stdout/stderr for better error reporting.
            result = subprocess.run(
                command,
                cwd=PROCESS_DIR,
                check=True,
                capture_output=True,
                text=True
            )
            # You can uncomment the following line to see the output of each script
            # print(result.stdout)

        except FileNotFoundError:
            print(f"FATAL ERROR: The directory '{PROCESS_DIR}' was not found.")
            print("Please ensure you are running this script from your project's root directory.")
            return False
        except subprocess.CalledProcessError as e:
            print(f"\n!!!!!!!!!! ERROR ENCOUNTERED !!!!!!!!!!!")
            print(f"  SCRIPT FAILED: {command_str}")
            print(f"  RETURN CODE: {e.returncode}")
            print("----------------- STDOUT -----------------")
            print(e.stdout)
            print("----------------- STDERR -----------------")
            print(e.stderr)
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n")
            return False

    return True


if __name__ == "__main__":
    # Verify that the target directory exists before starting.
    if not os.path.isdir(PROCESS_DIR):
        print(f"FATAL ERROR: The directory '{PROCESS_DIR}' does not exist.")
        print("Please ensure you are running this script from your project's root directory.")
        sys.exit(1)

    for i in range(1, NUM_RUNS + 1):
        print(f"\n==================================================")
        print(f"  STARTING WORKFLOW RUN #{i} of {NUM_RUNS}")
        print(f"==================================================")

        success = run_single_workflow(run_number=i)

        if success:
            print(f"--------------------------------------------------")
            print(f"  SUCCESS: WORKFLOW RUN #{i} COMPLETED")
            print(f"--------------------------------------------------")
        else:
            print(f"--------------------------------------------------")
            print(f"  FAILURE: WORKFLOW RUN #{i} FAILED. Halting all runs.")
            print(f"--------------------------------------------------")
            # Stop the entire process if one run fails
            sys.exit(1)

    print(f"\n==================================================")
    print(f"  ALL {NUM_RUNS} WORKFLOW RUNS FINISHED SUCCESSFULLY")
    print(f"==================================================")

