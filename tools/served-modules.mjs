// Load the interface the way a browser does: over HTTP, from the running server.
//
// Both harnesses used to import the modules straight off the filesystem:
//
//   const modules = new URL('../src/vcqi/web/static/js/', import.meta.url);
//
// which tests the code and not the delivery. That gap let a real failure through. A
// browser was serving a cached `app.js` beside a freshly fetched `chapters.js`, the two
// disagreed about the render context, and chapter 0 showed "context.text is not a
// function" — while `ui-clicks.mjs`, reading both files from disk, reported that every
// control on every chapter responded. Twice.
//
// So the bytes under test are now the bytes the server sends. Node cannot import an
// http: URL without a flag that has come and gone between releases, so they are
// downloaded to a temporary directory and imported from there; the modules import each
// other with relative specifiers, so keeping them together is all that is needed.
//
// The file *names* still come from the working tree, because HTTP offers no directory
// listing. That is the right way round: a module that exists on disk and does not come
// back over HTTP is exactly the failure this is here to catch, and it fails loudly.

import { mkdtemp, readdir, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const SOURCE = new URL('../src/vcqi/web/static/js/', import.meta.url);

// A browser refuses to execute a module served as anything else, so a wrong type here
// is a broken page even when the bytes are perfect.
const JAVASCRIPT = /^(application|text)\/javascript\b/;

/**
 * Download every interface module from a running server.
 *
 * @param {string} base  origin of the server, e.g. http://127.0.0.1:8000
 * @returns {Promise<URL>}  directory URL to import the modules from
 */
export async function servedModules(base) {
  const names = (await readdir(fileURLToPath(SOURCE))).filter((name) => name.endsWith('.js'));
  if (!names.length) throw new Error(`no modules found in ${fileURLToPath(SOURCE)}`);

  const directory = await mkdtemp(join(tmpdir(), 'vcqi-served-'));
  const problems = [];

  for (const name of names) {
    const address = `${base}/static/js/${name}`;
    let response;
    try {
      response = await fetch(address);
    } catch (error) {
      problems.push(`${name}: ${error.message}`);
      continue;
    }
    if (!response.ok) {
      problems.push(`${name}: ${response.status} ${response.statusText} from ${address}`);
      continue;
    }
    const type = response.headers.get('content-type') || '';
    if (!JAVASCRIPT.test(type)) {
      problems.push(`${name}: served as '${type}', which a browser will not execute`);
      continue;
    }
    await writeFile(join(directory, name), await response.text());
  }

  if (problems.length) {
    throw new Error(
      `the server did not deliver the interface:\n  ${problems.join('\n  ')}\n` +
        'These files exist in the working tree, so this is a delivery problem rather ' +
        'than a missing module.'
    );
  }

  return pathToFileURL(join(directory, 'index.js'));
}
