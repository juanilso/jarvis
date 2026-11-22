<?php
/*
 * Roteador da prévia do Jarvis (php -S ... jarvis-roteador.php).
 * Imita o que o .htaccess costuma fazer no cPanel, para o site abrir igual ao publicado:
 *  - arquivo que existe: servido normalmente (CSS, JS, imagens, .php);
 *  - /contato  ->  contato.php, contato.html ou contato.htm (URLs sem extensão);
 *  - sites com "front controller" (Laravel, CodeIgniter, WordPress, .htaccess mandando tudo para index.php):
 *    qualquer caminho que não é arquivo vai para index.php;
 *  - o resto: 404 de verdade (para o teste achar o link quebrado).
 */
$raiz = realpath($_SERVER['DOCUMENT_ROOT']);
$uri = urldecode(parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH) ?: '/');

function dentro($caminho, $raiz) {
    return $caminho !== false && ($caminho === $raiz || strpos($caminho, $raiz . DIRECTORY_SEPARATOR) === 0);
}

function rodar_php($arquivo, $uri_script) {
    $_SERVER['SCRIPT_NAME'] = $uri_script;
    $_SERVER['PHP_SELF'] = $uri_script;
    $_SERVER['SCRIPT_FILENAME'] = $arquivo;
    chdir(dirname($arquivo));
    require $arquivo;
    return true;
}

$alvo = realpath($raiz . $uri);
if (dentro($alvo, $raiz)) {
    if (is_file($alvo)) {
        return false;                       // o servidor do PHP entrega o arquivo (ou executa o .php)
    }
    if (is_dir($alvo)) {
        foreach (['index.php', 'index.html', 'index.htm'] as $i) {
            if (is_file($alvo . DIRECTORY_SEPARATOR . $i)) {
                return false;
            }
        }
    }
}

// URL sem extensão (/contato -> contato.php / contato.html)
$sem = rtrim($uri, '/');
if ($sem !== '') {
    foreach (['.php', '.html', '.htm'] as $ext) {
        $f = realpath($raiz . $sem . $ext);
        if (dentro($f, $raiz) && is_file($f)) {
            if ($ext === '.php') {
                return rodar_php($f, $sem . $ext);
            }
            header('Content-Type: text/html; charset=utf-8');
            readfile($f);
            return true;
        }
    }
}

// front controller: só quando o site realmente usa (senão um link quebrado viraria a página inicial)
$index = $raiz . DIRECTORY_SEPARATOR . 'index.php';
$ht = @file_get_contents($raiz . DIRECTORY_SEPARATOR . '.htaccess') ?: '';
$framework = preg_match('/RewriteRule\s+.*index\.php/i', $ht)
    || is_file(dirname($raiz) . DIRECTORY_SEPARATOR . 'artisan')
    || is_file($raiz . DIRECTORY_SEPARATOR . 'wp-config.php')
    || is_dir($raiz . DIRECTORY_SEPARATOR . 'system') && is_dir($raiz . DIRECTORY_SEPARATOR . 'application');
if ($framework && is_file($index)) {
    return rodar_php($index, '/index.php');
}
// 404 de verdade (o php -S, sozinho, devolveria a index.php para qualquer endereço e esconderia o link quebrado)
http_response_code(404);
header('Content-Type: text/html; charset=utf-8');
$h = htmlspecialchars($uri, ENT_QUOTES, 'UTF-8');
echo "<!doctype html><html lang=\"pt-BR\"><meta charset=\"utf-8\"><title>404 · não encontrado</title>"
   . "<body style=\"font-family:sans-serif;padding:40px\"><h1>404 · página não encontrada</h1>"
   . "<p>A prévia do Jarvis não achou <code>$h</code> neste projeto.</p></body></html>";
return true;
