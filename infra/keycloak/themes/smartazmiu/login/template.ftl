<#import "footer.ftl" as loginFooter>
<#macro registrationLayout bodyClass="" displayInfo=false displayMessage=true displayRequiredFields=false>
<!DOCTYPE html>
<html class="${properties.kcHtmlClass!}" lang="${lang}">

<head>
    <meta charset="utf-8">
    <#if properties.meta?has_content>
        <#list properties.meta?split(' ') as meta>
            <meta name="${meta?split('==')[0]}" content="${meta?split('==')[1]}"/>
        </#list>
    </#if>
    <meta name="robots" content="noindex, nofollow">
    <title>${msg("saPageTitle")}</title>
    <link rel="icon" href="${url.resourcesPath}/img/favicon.svg" type="image/svg+xml" />
    <#if properties.styles?has_content>
        <#list properties.styles?split(' ') as style>
            <link href="${url.resourcesPath}/${style}" rel="stylesheet" />
        </#list>
    </#if>
    <script type="importmap">
        {
            "imports": {
                "rfc4648": "${url.resourcesCommonPath}/vendor/rfc4648/rfc4648.js"
            }
        }
    </script>
    <#if scripts??>
        <#list scripts as script>
            <script src="${script}" type="text/javascript"></script>
        </#list>
    </#if>
    <script type="module">
        <#outputformat "JavaScript">
        import { startSessionPolling } from ${(url.resourcesPath + "/js/authChecker.js")?c};

        startSessionPolling(
            ${url.ssoLoginInOtherTabsUrl?c}
        );
        </#outputformat>
    </script>
    <#if authenticationSession??>
        <script type="module">
            <#outputformat "JavaScript">
            import { checkAuthSession } from ${(url.resourcesPath + "/js/authChecker.js")?c};

            checkAuthSession(
                ${authenticationSession.authSessionIdHash?c}
            );
            </#outputformat>
        </script>
    </#if>
</head>

<body class="${properties.kcBodyClass!} ${bodyClass}" data-page-id="login-${pageId}">
<a class="sa-skip-link" href="#kc-content">${msg("saSkipToContent")}</a>

<header class="sa-topbar">
    <span class="sa-wordmark">SmartAzMİU</span>
</header>

<main id="kc-content" class="sa-main" tabindex="-1">
    <section class="sa-panel" aria-labelledby="kc-page-title">
        <#if !(auth?has_content && auth.showUsername() && !auth.showResetCredentials())>
            <h1 id="kc-page-title" class="sa-title"><#nested "header"></h1>
        <#else>
            <#nested "show-username">
            <h1 id="kc-page-title" class="sa-title"><#nested "header"></h1>
            <div id="kc-username" class="sa-attempted-user">
                <span id="kc-attempted-username">${auth.attemptedUsername}</span>
                <a id="reset-login" class="sa-link" href="${url.loginRestartFlowUrl}">${msg("saChangeUser")}</a>
            </div>
        </#if>

        <#if displayRequiredFields>
            <p class="sa-required-note"><span class="sa-required" aria-hidden="true">*</span> ${msg("requiredFields")}</p>
        </#if>

        <#-- App-initiated actions should not see warnings about the action they are completing. -->
        <#if displayMessage && message?has_content && (message.type != 'warning' || !isAppInitiatedAction??)>
            <div class="sa-banner sa-banner-${message.type}" role="<#if message.type = 'error'>alert<#else>status</#if>">
                <span class="sa-icon <#if message.type = 'error'>sa-icon-alert<#elseif message.type = 'success'>sa-icon-check<#else>sa-icon-info</#if>" aria-hidden="true"></span>
                <span class="sa-banner-text">${kcSanitize(message.summary)?no_esc}</span>
            </div>
        </#if>

        <#nested "form">

        <#if auth?has_content && auth.showTryAnotherWayLink()>
            <form id="kc-select-try-another-way-form" action="${url.loginAction}" method="post">
                <div class="sa-field">
                    <input type="hidden" name="tryAnotherWay" value="on"/>
                    <button type="submit" id="try-another-way" class="sa-button sa-button-tertiary">${msg("doTryAnotherWay")}</button>
                </div>
            </form>
        </#if>

        <#nested "socialProviders">

        <#if displayInfo>
            <div id="kc-info" class="${properties.kcSignUpClass!}">
                <div id="kc-info-wrapper" class="${properties.kcInfoAreaWrapperClass!}">
                    <#nested "info">
                </div>
            </div>
        </#if>
    </section>

    <p class="sa-help">${msg("saHelp")}</p>
    <@loginFooter.content/>
</main>
</body>
</html>
</#macro>
