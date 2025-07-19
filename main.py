import subprocess
import os
import sys
import shutil
from datetime import datetime

# --- Configuration ---
# Set the number of times you want the entire workflow to run
NUM_RUNS = 20

# Set the relative path to the directory containing the scripts to be executed
PROCESS_DIR = "src/cyberdata/process"

# Define the sequence of commands to run for one workflow cycle.
# These commands are run from within the PROCESS_DIR.
WORKFLOW_STEPS = [
    [sys.executable, "problems.py"],
    [sys.executable, "extend_problems.py"],
    [sys.executable, "small_dataset.py"],
    [sys.executable, "validate_small.py"],
    [sys.executable, "generator.py"],
    # [sys.executable, "generator.py"],
    [sys.executable, "validate_large.py"],
]

# --- Archiving Configuration ---
# The main directory where results will be saved.
# This path is relative to where you run the script (your project root).
ARCHIVE_DIR = "archived_json_data"

# List of files/folders to save after each successful run.
# IMPORTANT: These paths are now relative to your project's root directory.
ITEMS_TO_ARCHIVE = [
    "config",
    "data/large_samples",
    "data/quality_reports",
    "data/seeds",
    "data/validation_reports"  # Example of a folder to archive
]

# --- Cleanup Configuration ---
# List of files/folders to delete after a successful archive to prepare for the next run.
# These paths are relative to your project's root directory.
ITEMS_TO_CLEANUP = [
    "data/large_samples",
    "data/quality_reports",
    "data/seeds",
    "data/validation_reports",
    "config/problems_updated.json",
    "config/problems.json",
    "config/problems_evaluation_report.json"

]


def run_single_workflow(run_number: int):
    """
    Executes one full cycle of the data generation workflow.
    """
    for i, command in enumerate(WORKFLOW_STEPS):
        step_num = i + 1
        command_str = " ".join(command)
        print(f"[RUN {run_number}/STEP {step_num}] Executing: {command_str}")

        try:
            subprocess.run(
                command,
                cwd=PROCESS_DIR,
                check=True,
                capture_output=True,
                text=True
            )
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


def archive_results(run_number: int, unique_id: str):
    """
    Saves specified files and folders to a unique archive directory.
    """
    print(f"--- Archiving results for RUN #{run_number} ---")
    archive_path = os.path.join(ARCHIVE_DIR, unique_id)
    try:
        os.makedirs(archive_path, exist_ok=True)
        print(f"Created archive directory: {archive_path}")

        for item_to_archive in ITEMS_TO_ARCHIVE:
            source_path = item_to_archive
            dest_path = os.path.join(archive_path, os.path.basename(source_path))

            if not os.path.exists(source_path):
                print(f"  - WARNING: Cannot find '{source_path}' to archive. Skipping.")
                continue

            if os.path.isdir(source_path):
                shutil.copytree(source_path, dest_path)
                print(f"  - Archived directory: '{source_path}'")
            else:
                shutil.copy2(source_path, dest_path)
                print(f"  - Archived file: '{source_path}'")
        return True
    except Exception as e:
        print(f"\n!!!!!!!!!! ARCHIVING FAILED !!!!!!!!!!!")
        print(f"  Could not archive results for RUN #{run_number}.")
        print(f"  ERROR: {e}")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n")
        return False


def cleanup_after_run(run_number: int):
    """
    Deletes specified files and folders to clean the workspace.
    This function is robust and will not fail if items are already deleted.
    """
    print(f"--- Cleaning up workspace after RUN #{run_number} ---")
    for item_path in ITEMS_TO_CLEANUP:
        try:
            if not os.path.exists(item_path):
                # It's fine if the item doesn't exist, just skip it.
                continue

            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
                print(f"  - Deleted directory: '{item_path}'")
            elif os.path.isfile(item_path):
                os.remove(item_path)
                print(f"  - Deleted file: '{item_path}'")
        except Exception as e:
            # Log error but don't stop the whole process
            print(f"  - WARNING: Could not clean up '{item_path}'. Reason: {e}")
    print("--- Cleanup complete ---")
    return True


if __name__ == "__main__":
    if not os.path.isdir(PROCESS_DIR):
        print(f"FATAL ERROR: The process directory '{PROCESS_DIR}' does not exist.")
        print("Please ensure you are running this script from your project's root directory.")
        sys.exit(1)

    os.makedirs(ARCHIVE_DIR, exist_ok=True)

    for i in range(1, NUM_RUNS + 1):
        try:
            print(f"\n==================================================")
            print(f"  STARTING WORKFLOW RUN #{i} of {NUM_RUNS}")
            print(f"==================================================")

            success = run_single_workflow(run_number=i)

            if success:
                unique_folder_name = f"run_{i}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                archiving_success = archive_results(run_number=i, unique_id=unique_folder_name)
                
                if archiving_success:
                    print(f"--------------------------------------------------")
                    print(f"  SUCCESS: WORKFLOW RUN #{i} COMPLETED & ARCHIVED")
                    print(f"--------------------------------------------------")
                else:
                    # This case handles when the workflow is fine, but zipping/copying fails
                    print(f"--------------------------------------------------")
                    print(f"  WARNING: RUN #{i} COMPLETED, but ARCHIVING FAILED.")
                    print(f"--------------------------------------------------")
            else:
                # This case handles when a script in the workflow fails
                print(f"--------------------------------------------------")
                print(f"  FAILURE: WORKFLOW RUN #{i} FAILED. Halting all runs.")
                print(f"--------------------------------------------------")
                sys.exit(1) # The finally block will run before exiting

        finally:
            # THIS BLOCK WILL ALWAYS RUN at the end of each iteration,
            # regardless of success, failure, or archiving errors.
            print(f"\n--- Initiating Post-Run Cleanup for RUN #{i} ---")
            cleanup_after_run(run_number=i)

    print(f"\n==================================================")
    print(f"  ALL {NUM_RUNS} WORKFLOW RUNS FINISHED SUCCESSFULLY")
    print(f"==================================================")