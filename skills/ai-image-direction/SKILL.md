---
name: ai-image-direction
description: Generate site photography that looks like a real photographer took it, not like AI made it — the always-include phrases, the negative prompt, composition rules, and the list of images never to generate at all. Use before generating any image for a client website, hero, blog header, share card or section background, and when a generated image looks glossy, plastic or synthetic. Triggers on "image banao", "generate image", "hero image", "photo chahiye", "AI image", "og image", "banner", "stock photo".
---

# Directing AI photography

A client once called a mockup "designed by AI". Images are where that judgement
is made first, before a word is read.

## The core rule

Every generated image must look like **real photography taken by a human on a
real assignment**. Not illustrated, not rendered, not CGI.

## Always include, in every image prompt

```
editorial documentary photograph, natural available light, shot on 35mm lens,
shallow depth of field, subtle film grain, muted natural colour grading,
candid unposed moment, realistic textures, photojournalistic
```

## Always exclude, in every image prompt

```
no 3D render, no CGI, no digital illustration, no vector art, no glowing neon,
no holograms, no floating UI panels, no futuristic overlays, no circuit-board
patterns, no robot hands, no glowing globes, no oversaturated colours, no HDR
look, no lens flare, no heavy vignette, no text, no words, no letters, no logos,
no watermarks, no perfectly symmetrical corporate stock-photo composition,
no distorted hands, no extra fingers
```

Add the cliches of the client's own industry. For a sustainability client those
were: `no cliche of hands cradling a seedling, no cupped soil, no green leaf
overlaid on a city, no smiling people staring at a laptop together`. Every
sector has its three or four; name them explicitly or the model will reach for
them.

## Composition

- **Prefer environments, architecture, materials and details over faces.**
  Faces are where generation fails most visibly. If people appear, show them
  small in frame, from behind, in profile, or cropped. Never a large
  front-facing portrait.
- The palette must sit naturally beside the brand. Name the actual colours:
  "deep greens, warm neutrals, muted slate blues, concrete greys. Nothing neon
  or acid green."
- Leave calm negative space. These sit inside a layout, not on their own.
- Landscape 16:9 unless the slot says otherwise. Export WebP with a JPEG
  fallback.
- Write the alt text in the same breath as the prompt, describing what the
  image shows in the context of the page.

## What not to generate at all

This list saves more than the prompts do:

- **No hero background image** when the hero is typographic. If the brief says
  minimal clutter, the hero is text and whitespace, and adding a photo fights
  the brief.
- **No icons.** Use a line-icon set such as lucide-react. A generated image used
  as an icon always looks wrong next to real ones.
- **No portraits of team members.** Use the real photographs the client
  supplied, or leave a marked placeholder.
- **No images for content that is not published yet.**
- **No og:image photo.** Build the share card in code instead: brand background,
  the real logo, a typographic headline, a thin rule. Clean, on-brand, and it
  never looks synthetic. See the `launch-files` skill for where it must live.

## After generating

Look at every image and regenerate any that is glossy, plastic, rendered or
obviously synthetic.

Regenerate automatically if the image contains **any visible text** or a
**distorted hand**. Those two are the giveaways a client notices immediately.

Then check the set together, not one by one: do they look like they came from
the same shoot? A mixed set reads as stock, which is its own kind of cheap.

## Licensing, if a real photo is used instead

A supplied or stock photo needs a licence that covers commercial client use.
Record where it came from and under what licence in the project's memory. Never
pull an image off a competitor's site or a search result.
