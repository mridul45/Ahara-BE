# Ahara

**The future of health and wellness.**

[![Built with Cookiecutter Django](https://img.shields.io/badge/built%20with-Cookiecutter%20Django-ff69b4.svg?logo=cookiecutter)](https://github.com/cookiecutter/cookiecutter-django/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Table of Contents

- [About The Project](#about-the-project)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
- [Testing & Code Quality](#testing--code-quality)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [License](#license)

---

## About The Project

Ahara is a Django-based web application designed to be the future of health and wellness. This project is built using the robust `cookiecutter-django` template, ensuring a production-ready setup from the start.

## Features

-   **User Authentication:** Complete user management system including sign-up, login, logout, and email verification, powered by `django-allauth`.
-   **OTP Based Login:** Secure OTP-based login system.
-   **OTP Expiration:** OTPs expire after 10 minutes for enhanced security.
-   **User Profile:** User profiles with avatars and other details.
-   **RESTful API:** A comprehensive REST API built with `djangorestframework` for seamless integration with other services.
-   **Static Asset Management:** Optimized static file handling with `whitenoise` and `django-compressor`.
-   **Asynchronous Tasks:** Ready for background tasks with Celery (if configured).
-   **Secure by Default:** Strong security practices, including environment-based settings and `argon2` password hashing.

## Tech Stack

-   **Backend:** [Python](https://www.python.org/), [Django](https://www.djangoproject.com/)
-   **Database:** [PostgreSQL](https://www.postgresql.org/)
-   **API:** [Django REST Framework](https://www.django-rest-framework.org/)
-   **Authentication:** [django-allauth](https://django-allauth.readthedocs.io/en/latest/)
-   **Deployment:** [Gunicorn](https://gunicorn.org/), [Render](https://render.com/)
-   **Code Quality:** [Ruff](https://github.com/astral-sh/ruff), [mypy](http://mypy-lang.org/), [pytest](https://docs.pytest.org/en/stable/)

## Getting Started

To get a local copy up and running, follow these simple steps.

### Prerequisites

Make sure you have the following installed on your local machine:

-   Python 3.12+
-   PostgreSQL
-   Redis (for caching and session storage)
-   A virtual environment tool (`venv`, `virtualenv`)

### Installation

1.  **Clone the repository:**
    ```sh
    git clone https://github.com/your_username/ahara.git
    cd ahara
    ```

2.  **Create and activate a virtual environment:**
    ```sh
    python -m venv env
    source env/bin/activate
    ```

3.  **Install dependencies:**
    For local development, use the `local.txt` requirements file.
    ```sh
    pip install -r requirements/local.txt
    ```

4.  **Set up your environment variables:**
    Copy the example `.env` file and fill in your local configuration.
    ```sh
    cp .env.example .env
    ```
    You will need to configure `DATABASE_URL`, `REDIS_URL`, and other settings.

5.  **Run database migrations:**
    ```sh
    python manage.py migrate
    ```

6.  **Create a superuser:**
    To access the Django admin panel, you'''ll need a superuser account.
    ```sh
    python manage.py createsuperuser
    ```

7.  **Run the development server:**
    ```sh
    python manage.py runserver
    ```
    The application will be available at `http://127.0.0.1:8000`.

## Testing & Code Quality

This project uses a suite of tools to ensure high code quality.

-   **Run tests with `pytest`:**
    ```sh
    pytest
    ```

-   **Check test coverage:**
    ```sh
    coverage run -m pytest
    coverage html
    open htmlcov/index.html
    ```

-   **Run type checks with `mypy`:**
    ```sh
    mypy ahara
    ```

-   **Lint and format with `Ruff`:**
    ```sh
    ruff check .
    ruff format .
    ```

## Deployment

This application is configured for deployment on [Render](https://render.com/). The `render.yaml` file defines the services and the `build.sh` script handles the build process.

To deploy, connect your Git repository to Render and configure the services according to the `render.yaml` file.

## Contributing

Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

Please read `CONTRIBUTING.md` for details on our code of conduct, and the process for submitting pull requests to us.

## License

Distributed under the MIT License. See `LICENSE` for more information.