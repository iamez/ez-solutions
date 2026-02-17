## Summary

<!-- What does this PR do? Why? Link to the issue if applicable. -->
Closes #

---

## Type of change

- [ ] Bug fix (non-breaking)
- [ ] New feature (non-breaking)
- [ ] Breaking change (existing behaviour changes)
- [ ] Refactor / code quality
- [ ] Chore (deps, CI, docs)

---

## Checklist

### Code quality
- [ ] `ruff check .` passes locally
- [ ] `black --check .` passes locally
- [ ] No new `# noqa` suppressions without a comment explaining why

### Testing
- [ ] New/modified logic has tests
- [ ] All existing tests still pass (`pytest tests/ --no-cov -q`)
- [ ] No test uses real external services (Stripe, email, S3) — mocks only

### Security
- [ ] No secrets, keys, or passwords in code or comments
- [ ] Input validated / sanitised where user data is accepted
- [ ] Migrations are reversible (or documented why not)

### Django specifics
- [ ] `python manage.py check` passes
- [ ] New models have `__str__` and appropriate `Meta.ordering`
- [ ] New views are protected with `@login_required` / permissions if needed
- [ ] New URL patterns follow existing namespace conventions

### Documentation
- [ ] `.env.example` updated if new env vars added
- [ ] `requirements/base.txt` or `dev.txt` updated if dependencies added

---

## Screenshots (if UI changes)

<!-- Before / After screenshots or a short screen recording. -->
