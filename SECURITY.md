# Security

DeepRead is a local app. It is not a hosted service and does not have a private vulnerability-bounty inbox.

If you find a security issue in the reader or extractors (for example path traversal while ingesting notes, or unsafe handling of PDF/markdown input), please open a GitHub issue with a description and a non-exploitative reproduction. Do not attach copyrighted PDFs.

There are no production secrets in this repository. Do not commit `.env` files, API keys, or paths to private book files.
