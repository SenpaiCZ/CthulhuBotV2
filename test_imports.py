import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

try:
    print("Testing import of commands.versus...")
    import commands.versus
    print("Successfully imported commands.versus")

    print("Checking Versus class...")
    from commands.versus import Versus, VersusWizardView
    print("Versus class found.")
    print("VersusWizardView class found.")

except Exception as e:
    print(f"FAILED to import commands.versus: {e}")
    exit(1)

try:
    print("Testing import of commands.roll...")
    import commands.roll
    print("Successfully imported commands.roll")
except Exception as e:
    print(f"FAILED to import commands.roll: {e}")
    exit(1)

print("All checks passed.")
