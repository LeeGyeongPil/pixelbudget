"""Fit a tall screenshot to a token budget, or slice it into readable pieces."""

from pixelbudget import fit, plan_slices, slice_image

fitted = fit("samples/tall.png", "claude-standard", budget=800)
print("fit:", fitted.plan.size, fitted.plan.tokens, "tokens", fitted.plan.reason)

plan = plan_slices((1170, 9000), "claude-standard")
print("pieces:", len(plan.pieces), "of", plan.pieces[0].size, "=", plan.total_tokens, "tokens")

result = slice_image("samples/tall.png", "claude-standard")
print("images ready to send:", len(result.images), result.images[0].size)
