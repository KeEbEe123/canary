"""Auto-instrumentation adapters for popular agent/LLM libraries.

Each adapter is import-guarded so the SDK never hard-depends on the library it
wraps: ``canary.instrument("openai")`` is a no-op if ``openai`` isn't installed.
"""
