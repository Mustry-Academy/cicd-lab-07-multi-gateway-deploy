# The Part 1 skeleton

The smallest valid Perspective project: one view, one page route. Part 1A,
step 2 is literally:

```bash
cp -R projects/skeleton projects/<yourname>
rm projects/<yourname>/README.md
```

Then make it yours:

1. `project.json` — set `title` and `description`.
2. `com.inductiveautomation.perspective/views/welcome/view.json` — replace
   `YOUR NAME HERE` with your name.

This skeleton itself is never pinned in `release.yaml`, so it never deploys —
your copy only goes live once you tag it and pin it (Part 1B).
