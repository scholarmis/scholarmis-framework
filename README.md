# Scholarmis Framework

**Scholarmis Framework** is the **core Python/Django package** for Scholarmis, providing **shared utilities, base classes, and common components** used across all modules of the Scholarmis ecosystem.

It is designed to **reduce code duplication**, enforce **consistent patterns**, and serve as the foundation for modular educational management apps.

---

## Features

* **Common Utilities** – Logging, helpers, validators, and shared functions.
* **Base Models & Mixins** – Reusable Django models, abstract classes, and mixins.
* **Shared Services** – Centralized services like email, notifications, and file management.
* **Configuration & Settings** – Standardized settings management for all modules.
* **CLI Utilities** – Core commands used by multiple ScholarMIS modules.
* **Extensible & Lightweight** – Minimal dependencies, designed to be imported by any module.

---

## Installation

```bash
pip install scholarmis-framework
```

---

## Usage

Once installed, you can import and use the shared components in any module:

```python
from scholarmis.framework.models import BaseModel
```

* **BaseModel** – A reusable abstract Django model with common fields.
* **CLI** – Reuse core commands in module management scripts.

> The framework does not run standalone; it is meant to be imported by ScholarMIS modules.

---

## Contributing

We welcome contributions!

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

See [CONTRIBUTING.md](CONTRIBUTING.md) for more details.

---

## License

Scholarmis Framework is licensed under the **MIT License** – see [LICENSE](LICENSE).

---
