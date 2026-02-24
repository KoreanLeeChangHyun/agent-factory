# 기본 컴포넌트 템플릿

## 파일 구조
```
basicComponent/
├── basicComponent.html
├── basicComponent.js
├── basicComponent.css
└── basicComponent.js-meta.xml
```

## HTML (basicComponent.html)
```html
<template>
    <div class="container">
        <h2 class="title">{title}</h2>

        <template lwc:if={isLoading}>
            <div class="loading">Loading...</div>
        </template>

        <template lwc:elseif={hasError}>
            <div class="error">{errorMessage}</div>
        </template>

        <template lwc:else>
            <div class="content">
                <p>{description}</p>

                <div class="actions">
                    <button class="btn btn-primary" onclick={handleSave}>
                        Save
                    </button>
                    <button class="btn btn-secondary" onclick={handleCancel}>
                        Cancel
                    </button>
                </div>
            </div>
        </template>
    </div>
</template>
```

## JavaScript (basicComponent.js)
```javascript
import { LightningElement, api } from 'lwc';

export default class BasicComponent extends LightningElement {
    // Public Properties
    @api title = 'Default Title';
    @api description = '';

    // Private Properties
    isLoading = false;
    hasError = false;
    errorMessage = '';

    // Lifecycle Hooks
    connectedCallback() {
        this.loadData();
    }

    // Getters
    get hasContent() {
        return this.description && this.description.length > 0;
    }

    // Methods
    async loadData() {
        this.isLoading = true;
        try {
            // 데이터 로드 로직
            await this.fetchData();
        } catch (error) {
            this.hasError = true;
            this.errorMessage = error.message;
        } finally {
            this.isLoading = false;
        }
    }

    fetchData() {
        return new Promise(resolve => setTimeout(resolve, 1000));
    }

    // Event Handlers
    handleSave() {
        this.dispatchEvent(new CustomEvent('save', {
            detail: {
                title: this.title,
                description: this.description
            }
        }));
    }

    handleCancel() {
        this.dispatchEvent(new CustomEvent('cancel'));
    }
}
```

## CSS (basicComponent.css)
```css
:host {
    display: block;
}

.container {
    padding: 1.5rem;
    background-color: white;
    border: 1px solid #d8dde6;
    border-radius: 8px;
}

.title {
    margin: 0 0 1rem;
    font-size: 18px;
    font-weight: 600;
    color: #333;
}

.loading,
.error {
    padding: 2rem;
    text-align: center;
}

.error {
    color: #c23934;
}

.content {
    margin-bottom: 1rem;
}

.actions {
    display: flex;
    gap: 0.75rem;
    margin-top: 1.5rem;
}

.btn {
    padding: 0.75rem 1.5rem;
    font-size: 14px;
    font-weight: 500;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: background-color 0.2s ease;
}

.btn-primary {
    background-color: #0070d2;
    color: white;
}

.btn-primary:hover {
    background-color: #005fb2;
}

.btn-secondary {
    background-color: white;
    color: #0070d2;
    border: 1px solid #0070d2;
}

.btn-secondary:hover {
    background-color: #f4f6f9;
}
```

## Metadata (basicComponent.js-meta.xml)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<LightningComponentBundle xmlns="http://soap.sforce.com/2006/04/metadata">
    <apiVersion>59.0</apiVersion>
    <isExposed>true</isExposed>
    <targets>
        <target>lightning__RecordPage</target>
        <target>lightning__AppPage</target>
        <target>lightning__HomePage</target>
    </targets>
    <targetConfigs>
        <targetConfig targets="lightning__RecordPage,lightning__AppPage,lightning__HomePage">
            <property name="title" type="String" default="My Component"/>
            <property name="description" type="String"/>
        </targetConfig>
    </targetConfigs>
</LightningComponentBundle>
```

## 사용 예시
```html
<!-- 부모 컴포넌트에서 -->
<c-basic-component
    title="Account Details"
    description="View and edit account information"
    onsave={handleChildSave}
    oncancel={handleChildCancel}>
</c-basic-component>
```
