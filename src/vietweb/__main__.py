from .cli import main

# The guard matters on Windows: child processes (parallel.workers > 1) import this module again
if __name__ == "__main__":
    raise SystemExit(main())
