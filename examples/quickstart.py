"""Minimal offline example: no image files, just sizes."""

from pixelbudget import estimate, fit_size

# 1920x1080 on Claude's standard tier: the server shrinks it, so shrink it yourself first.
est = estimate((1920, 1080), "claude-standard")
print(f"claude-standard 1920x1080 -> {est.sent_size[0]}x{est.sent_size[1]} = {est.tokens} tokens")

# Largest size that costs at most 800 tokens.
plan = fit_size((1920, 1080), "claude-standard", budget=800)
print(f"fit_size budget=800 -> {plan.size[0]}x{plan.size[1]} = {plan.tokens} tokens ({plan.reason})")
