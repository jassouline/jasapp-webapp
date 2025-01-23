# Jasapp Webapp - A Web Interface for Jasapp

[![Build Status](https://github.com/jassouline/jasapp-webapp/actions/workflows/main.yml/badge.svg)](https://github.com/jassouline/jasapp-webapp/actions/workflows/main.yml)
This repository contains a web application (webapp) built with **FastAPI** that provides a user-friendly interface for **Jasapp**, a powerful static analysis tool (linter) designed for Dockerfiles and Kubernetes manifests.  

The webapp allows users to paste in their Dockerfile content and receive instant feedback on potential issues, along with a quality score. It leverages the core linting capabilities of the Jasapp linter and presents the results in an intuitive web interface.

## Features

-   **Dockerfile Linting:** Analyzes Dockerfiles using the comprehensive rule set from Jasapp.
-   **Live Feedback:**  Provides instant feedback as users type or paste their Dockerfile content (optional, requires JavaScript enhancements).
-   **Clear Error Presentation:** Displays errors and warnings with:
    -   Line numbers.
    -   Rule codes (e.g., `STX0001`, `SEC0003`, `PERF0006`).
    -   Descriptive messages.
    -   Severity levels (error, warning, info, style).
    -   Links to detailed rule documentation.
-   **Syntax Highlighting:** Integrates the Ace Editor for enhanced code readability with syntax highlighting.
-   **Quality Score:** Calculates and displays a quality score based on the detected issues.
-   **Modern UI:** Built with Tailwind CSS for a clean and responsive user interface.
-   **Easy Deployment:** Containerized with Docker for easy deployment.
-   **API Endpoint:** Provides an API endpoint (`/lint/dockerfile`) for integration with other tools.

## Prerequisites

-   **Docker:** You'll need Docker installed and running on your system to build and run the webapp.

## Installation & Usage

**1. Clone this repository:**

```bash
git clone https://github.com/jassouline/jasapp-webapp
cd jasapp-webapp
```

**2. Build the Docker image:**

```bash
docker build -t jasapp-webapp .
```

**3. Run the Docker container:**

```bash
docker run -d -p 8000:8000 jasapp-webapp
```

**4. Access the application:**
Open your web browser and navigate to http://localhost:8000.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

This project is licensed under the MIT License - see the LICENSE file for details.   


## Acknowledgements

- Jasapp - The core linter engine.
- Hadolint - Inspiration for many of the rules.
- FastAPI - The web framework used.
- Tailwind CSS - For styling.
- Ace Editor - For the code editor.