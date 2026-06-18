// Dedup store for already-uploaded gameIds, persisted across restarts.
//
// Choice: a single JSON file on disk rather than better-sqlite3.
// Rationale: the only state we need is a set of integer gameIds we have already uploaded
// successfully. A JSON array is trivially robust, has zero native build dependencies (sqlite
// needs node-gyp / a native binary that complicates install on user machines), and the data
// volume (a few thousand gameIds at most) is tiny. The reference uses sqlite because it also
// stores full game rows for its UI; this collector only needs a seen-set, so a JSON file is
// the simplest robust fit. Writes are atomic (write temp file, then rename).

import { promises as fs } from "node:fs";
import path from "node:path";

export class SeenStore {
  constructor(filePath) {
    this.filePath = filePath;
    this.ids = new Set();
  }

  async load() {
    try {
      const raw = await fs.readFile(this.filePath, "utf8");
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        for (const id of parsed) {
          this.ids.add(Number(id));
        }
      }
    }
    catch (err) {
      if (err.code !== "ENOENT") {
        console.warn(`[seen] could not read ${this.filePath} (${err.message}); starting empty`);
      }
    }
    return this;
  }

  has(gameId) {
    return this.ids.has(Number(gameId));
  }

  async add(gameId) {
    this.ids.add(Number(gameId));
    await this.persist();
  }

  async persist() {
    const dir = path.dirname(this.filePath);
    if (dir && dir !== ".") {
      await fs.mkdir(dir, { recursive: true });
    }
    const tmp = `${this.filePath}.tmp`;
    const data = JSON.stringify([...this.ids]);
    await fs.writeFile(tmp, data, "utf8");
    await fs.rename(tmp, this.filePath);
  }
}
