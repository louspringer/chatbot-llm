import os
import site
import sys

# Print current working directory
print("CWD:", os.getcwd())

# Print environment variables related to Python paths
print("\nPYTHONPATH:", os.environ.get("PYTHONPATH", "Not set"))
print(
    "AZURE_FUNCTIONS_ENVIRONMENT:",
    os.environ.get("AZURE_FUNCTIONS_ENVIRONMENT", "Not set"),
)

# Print Python executable location
print("\nPython executable:", sys.executable)

# Print all sys.path entries
print("\nsys.path contents:")
for path in sys.path:
    print(f"- {path}")

# Try to locate the specific botbuilder package
try:
    import botbuilder.core

    print(
        "\nBotbuilder.core location:",
        os.path.dirname(botbuilder.core.__file__),
    )
except ImportError as e:
    print("\nFailed to import botbuilder.core:", e)

    # Check if package exists in any sys.path location
    print("\nSearching for botbuilder in sys.path locations:")
    for path in sys.path:
        potential_path = os.path.join(path, "botbuilder")
        if os.path.exists(potential_path):
            print(f"Found botbuilder at: {potential_path}")
            # List contents of the botbuilder directory
            print("Contents:")
            for item in os.listdir(potential_path):
                print(f"  - {item}")

# Print site-packages directories
print("\nSite-packages directories:")
for path in site.getsitepackages():
    print(f"- {path}")
