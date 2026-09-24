// Тексты трактовок на Cloudflare Pages. Вся логика - в server/texts.js.

import natal from '../../web/content/interpretations.json';
import sky from '../../web/content/transits.json';
import checkFile from '../../web/content/checks.json';
import { flattenCheckTexts } from '../../web/checks.js';
import { handleTexts } from '../../server/texts.js';

const checks = { checks: flattenCheckTexts(checkFile) };

export const onRequestPost = ({ request }) => handleTexts(request, natal, sky, checks);
