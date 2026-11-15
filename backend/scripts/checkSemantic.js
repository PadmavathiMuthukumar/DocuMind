// backend/scripts/checkSemantic.js
// Run with:  npm run semantic:check   (the Python service must be running)

import { semanticService } from "../src/services/semanticService.js";

async function main() {
  const health = await semanticService.health();
  console.log("1. Python service is healthy:", health);

  const found = await semanticService.search({ query: "Which hackathons were won?" });
  console.log(`2. Question 1: no_match=${found.no_match}, results=${found.results.length}`);

  if (found.results[0]) {
    const best = found.results[0];
    console.log(`   Best: ${best.filename}, page ${best.page_number}, distance ${best.distance}`);
  } else {
    console.log(`   Message: ${found.message}`);
  }

  const unrelated = await semanticService.search({ query: "how to bake a chocolate cake" });
  console.log(`3. Question 2: no_match=${unrelated.no_match}, results=${unrelated.results.length}`);
}

main().catch((error) => {
  console.error(`Check failed: [${error.code ?? "ERROR"}] ${error.message}`);
  process.exitCode = 1;
});