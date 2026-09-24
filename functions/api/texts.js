// Тексты трактовок на Cloudflare Pages. Вся логика - в server/texts.js.

import natal from '../../web/content/interpretations.json';
import sky from '../../web/content/transits.json';
import { handleTexts } from '../../server/texts.js';

export const onRequestPost = ({ request }) => handleTexts(request, natal, sky);
