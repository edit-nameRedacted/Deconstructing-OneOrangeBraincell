/*
  text.js — the words that explain what the page shows. Edit freely: nothing here is computed.

    CATEGORY_TEXT  for each hand-code category: a sentence for the row view, and a line per value
                   (shown when a cat is zoomed). Taken from the coding rules in the data-handling
                   handoff; the "Has it" and "Seeking it" lines are drafts for AC to check.
    TAILVAR_TEXT   for each tail variable: what the number is (shown in the details panel).
    TAILS_OF_TEXT  the row sentence for a "Tails of …" view.

    MODEL_TEXT     the two models shown by the robot button: what each is, what it did, what
                   each stripe means, and how it compares with the hand ratings.

  The opening screen's text is in index.html (the <section id="intro">).
*/

// Names shown on the page in place of the data file's labels (which say "Dumbness (AC)" etc.).
export const DISPLAY_LABELS = {
  groupings: { dumb: "Dumbness", cute: "Cuteness" },
  tailvars: { ac_dumb: "Dumbness", ac_cute: "Cuteness" },
};

export const CATEGORY_TEXT = {
  braincell: {
    lede: "Grouped by whether the post shows the cat with the braincell.",
    values: {
      "Has it": "The cat has the braincell: it works something out or beats expectations.",           // draft
      "Had it": "The cat shows signs of usual or past competence, then slips.",
      "Seeking it": "The cat is trying to work something out, and the braincell hasn't arrived.",      // draft
      "What braincell?": "No sign of competence at all.",
      "Not applicable": "The post makes no claim about the cat's wits.",
    },
  },
  failure: {
    lede: "Grouped by what kind of thing went wrong for the cat.",
    values: {
      Self: "The cat versus itself: its tail, its reflection, its own body.",
      Physical: "Got stuck, fell, misjudged a jump.",
      Object: "Food, toys, doors.",
      Social: "With people or other animals.",
      NA: "Nothing went wrong: the post makes no claim about the cat's wits.",
    },
  },
  inferred: {
    lede: "Grouped by how you can tell whether the cat has the braincell.",
    values: {
      Actions: "From what the cat does.",
      Expression: "From the cat's face or posture.",
      Both: "From what it does and how it looks.",
      "Post context": "From the post's title: the joke is in the words, and the cat is a prop.",
      NA: "The post makes no claim about the cat's wits.",
    },
  },
  anthro: {
    lede: "Grouped by whether the post treats the cat as a person.",
    values: {
      "Just a cat": "Called by name or he/she, nothing more.",
      Kin: "Called son, boy, baby or child, with the poster as its parent.",
      Voiced: "Words are put in the cat's mouth.",
      "Kin and voiced": "Both: family member and speaker.",
    },
  },
  dumb: {
    lede: "Grouped by how dumb the cat comes across, rated by hand from 1 (not at all) to 5 (very).",
    values: {},
  },
  cute: {
    lede: "Grouped by how cute the cat is, rated by hand from 1 (not very) to 5 (very).",
    values: {},
  },
};

export const TAILVAR_TEXT = {
  score: "The post's upvotes (net score) when it was archived.",
  comments: "How many comments the post drew.",
  score_rel: "Upvotes per 1,000 subscribers at the time. The community more than tripled over the summer, so this evens out early and late posts.",
  talk: "Comments per 100 upvotes: how much talk a post drew for how popular it was.",
  crossposts: "How many times the post was shared to other subreddits.",
  awards: "Reddit awards the post received.",
  rank: "The post's place among its month's top 40 (1 is the top).",
  ac_dumb: "How dumb the cat comes across, rated by hand from 1 to 5.",
  ac_cute: "How cute the cat is, rated by hand from 1 to 5.",
  look_white: "Share of the cat's coat that is white, estimated by the vision model.",
  look_kg: "The cat's weight, estimated by the vision model.",
};

export function TAILS_OF_TEXT(label) {
  return `Grouped by where each post falls on ${label.toLowerCase()}: the lowest 10% (left tail), the middle 80% (body), and the highest 10% (right tail).`;
}

// The two models behind the robot button ("What a model trained on the internet thinks of this
// group"). Facts from oobc_archive/ai_opinion (tokenprobs/run_tokenprobs.py, siglip_scores.py) and
// the stage 2 results (oobc_archive/final_codes/stage2_results.md).
export const MODEL_TEXT = {
  qwen: {
    name: "Qwen 3.5 (9B)",
    kind: "A language model that can read pictures",
    how: "It was shown each post's photos with its reply already started, “This cat is so…” or “What a…”, and asked only for the next word. Its likely words were sorted into five families. Each stripe is how much of its next-word odds went to that family, averaged over the group's posts.",
    stripes: {
      cute: "Cute words (cute, adorable, sweet…)",
      funny: "Funny words (funny, silly, goofy…)",
      calm: "Calm words (relaxed, cozy, sleepy…)",
      body: "Body words (fluffy, chubby, round…)",
      mind: "Mind words (curious, focused, confused…)",
    },
    shortStripes: { cute: "Cute words", funny: "Funny words", calm: "Calm words", body: "Body words", mind: "Mind words" },
    compare: "How it lines up with the hand ratings: the more it leans to funny over cute words, the higher the post's hand-rated Dumbness (Spearman ρ = +0.29 over 147 posts, predicted in advance).",
  },
  siglip: {
    name: "SigLIP 2",
    kind: "An image–caption matching model",
    how: "It scores how well an image matches a caption. Each post's images were compared against pairs of opposite captions, such as “a derpy cat” and “a dignified cat”. Each stripe is how far this group's cats lean toward the first caption, as a percentile of all 182 posts.",
    stripes: {
      dumb: "Dumb (vs smart)",
      cute: "Cute (vs ugly)",
      fat: "Fat (vs skinny)",
      derp: "Derpy (vs dignified)",
      blank: "Blank stare (vs thinking hard)",
      loaf: "Loaf of bread (vs cat)",
    },
    shortStripes: { dumb: "Dumb", cute: "Cute", fat: "Fat", derp: "Derpy", blank: "Blank stare", loaf: "Loaf" },
    compare: "How it lines up with the hand ratings: the more derpy than dignified it finds a cat, the higher the post's hand-rated Dumbness (Spearman ρ = +0.42 over 147 posts, predicted in advance).",
  },
};
