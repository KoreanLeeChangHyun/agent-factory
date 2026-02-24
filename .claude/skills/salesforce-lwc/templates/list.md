# 리스트 컴포넌트 템플릿

## HTML (customList.html)
```html
<template>
    <div class="list-container">
        <!-- 헤더 -->
        <div class="list-header">
            <h3 class="list-title">{title}</h3>
            <span class="list-count">{itemCount} items</span>
        </div>

        <!-- 검색 & 필터 -->
        <div class="list-toolbar">
            <div class="search-box">
                <input
                    type="text"
                    class="search-input"
                    placeholder="Search..."
                    value={searchTerm}
                    onkeyup={handleSearch}>
            </div>
            <div class="filter-box">
                <select class="filter-select" onchange={handleFilter}>
                    <option value="">All</option>
                    <template for:each={filterOptions} for:item="option">
                        <option key={option.value} value={option.value}>
                            {option.label}
                        </option>
                    </template>
                </select>
            </div>
        </div>

        <!-- 로딩 -->
        <template lwc:if={isLoading}>
            <div class="list-loading">
                <div class="spinner"></div>
                <span>Loading...</span>
            </div>
        </template>

        <!-- 빈 상태 -->
        <template lwc:elseif={isEmpty}>
            <div class="list-empty">
                <p>No items found</p>
            </div>
        </template>

        <!-- 리스트 -->
        <template lwc:else>
            <ul class="list">
                <template iterator:it={filteredItems}>
                    <li key={it.value.id} class="list-item">
                        <template lwc:if={it.first}>
                            <span class="badge badge-first">First</span>
                        </template>

                        <div class="item-content">
                            <div class="item-main">
                                <span class="item-name">{it.value.name}</span>
                                <span class="item-type">{it.value.type}</span>
                            </div>
                            <div class="item-secondary">
                                {it.value.description}
                            </div>
                        </div>

                        <div class="item-actions">
                            <button
                                class="btn-icon"
                                data-id={it.value.id}
                                onclick={handleEdit}
                                title="Edit">
                                Edit
                            </button>
                            <button
                                class="btn-icon btn-danger"
                                data-id={it.value.id}
                                onclick={handleDelete}
                                title="Delete">
                                Delete
                            </button>
                        </div>

                        <template lwc:if={it.last}>
                            <span class="badge badge-last">Last</span>
                        </template>
                    </li>
                </template>
            </ul>

            <!-- 페이지네이션 -->
            <template lwc:if={showPagination}>
                <div class="pagination">
                    <button
                        class="btn-page"
                        disabled={isFirstPage}
                        onclick={handlePrevPage}>
                        Previous
                    </button>
                    <span class="page-info">
                        Page {currentPage} of {totalPages}
                    </span>
                    <button
                        class="btn-page"
                        disabled={isLastPage}
                        onclick={handleNextPage}>
                        Next
                    </button>
                </div>
            </template>
        </template>
    </div>
</template>
```

## JavaScript (customList.js)
```javascript
import { LightningElement, api, track } from 'lwc';

export default class CustomList extends LightningElement {
    @api title = 'Items';
    @api pageSize = 10;

    @track items = [];

    isLoading = false;
    searchTerm = '';
    filterValue = '';
    currentPage = 1;

    filterOptions = [
        { label: 'Active', value: 'active' },
        { label: 'Inactive', value: 'inactive' }
    ];

    connectedCallback() {
        this.loadItems();
    }

    // Getters
    get filteredItems() {
        let result = [...this.items];

        // 검색 필터
        if (this.searchTerm) {
            const term = this.searchTerm.toLowerCase();
            result = result.filter(item =>
                item.name.toLowerCase().includes(term) ||
                item.description?.toLowerCase().includes(term)
            );
        }

        // 타입 필터
        if (this.filterValue) {
            result = result.filter(item => item.status === this.filterValue);
        }

        // 페이지네이션
        const start = (this.currentPage - 1) * this.pageSize;
        const end = start + this.pageSize;

        return result.slice(start, end);
    }

    get itemCount() {
        return this.items.length;
    }

    get isEmpty() {
        return this.filteredItems.length === 0;
    }

    get totalPages() {
        return Math.ceil(this.items.length / this.pageSize);
    }

    get showPagination() {
        return this.totalPages > 1;
    }

    get isFirstPage() {
        return this.currentPage === 1;
    }

    get isLastPage() {
        return this.currentPage >= this.totalPages;
    }

    // Methods
    async loadItems() {
        this.isLoading = true;
        try {
            // API 호출 (예시 데이터)
            await new Promise(resolve => setTimeout(resolve, 500));
            this.items = [
                { id: '1', name: 'Item 1', type: 'Type A', description: 'Description 1', status: 'active' },
                { id: '2', name: 'Item 2', type: 'Type B', description: 'Description 2', status: 'inactive' },
                { id: '3', name: 'Item 3', type: 'Type A', description: 'Description 3', status: 'active' },
                // ...more items
            ];
        } catch (error) {
            console.error('Error loading items:', error);
        } finally {
            this.isLoading = false;
        }
    }

    // Event Handlers
    handleSearch(event) {
        this.searchTerm = event.target.value;
        this.currentPage = 1;
    }

    handleFilter(event) {
        this.filterValue = event.target.value;
        this.currentPage = 1;
    }

    handleEdit(event) {
        const itemId = event.currentTarget.dataset.id;
        this.dispatchEvent(new CustomEvent('edit', {
            detail: { id: itemId }
        }));
    }

    handleDelete(event) {
        const itemId = event.currentTarget.dataset.id;
        // Note: confirm()은 브라우저 네이티브 대화상자로 Lightning Experience 스타일과 맞지 않음.
        // 프로덕션에서는 커스텀 모달 컴포넌트(modal.md 참조) 사용을 권장합니다.
        // 아래는 간단한 예시를 위한 코드입니다.
        this.dispatchEvent(new CustomEvent('confirmdelete', {
            detail: { id: itemId }
        }));
    }

    handlePrevPage() {
        if (this.currentPage > 1) {
            this.currentPage--;
        }
    }

    handleNextPage() {
        if (this.currentPage < this.totalPages) {
            this.currentPage++;
        }
    }

    // Public Methods
    @api
    refresh() {
        this.loadItems();
    }

    @api
    setItems(items) {
        this.items = items;
    }
}
```

## CSS (customList.css)
```css
:host {
    display: block;
}

.list-container {
    background-color: white;
    border: 1px solid #d8dde6;
    border-radius: 8px;
    overflow: hidden;
}

.list-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 1.5rem;
    background-color: #f4f6f9;
    border-bottom: 1px solid #d8dde6;
}

.list-title {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
}

.list-count {
    font-size: 14px;
    color: #706e6b;
}

.list-toolbar {
    display: flex;
    gap: 1rem;
    padding: 1rem 1.5rem;
    border-bottom: 1px solid #d8dde6;
}

.search-box {
    flex: 1;
}

.search-input {
    width: 100%;
    padding: 0.5rem 1rem;
    border: 1px solid #d8dde6;
    border-radius: 4px;
    font-size: 14px;
}

.filter-select {
    padding: 0.5rem 1rem;
    border: 1px solid #d8dde6;
    border-radius: 4px;
    font-size: 14px;
    min-width: 150px;
}

.list-loading,
.list-empty {
    padding: 3rem;
    text-align: center;
    color: #706e6b;
}

.spinner {
    width: 24px;
    height: 24px;
    border: 2px solid #d8dde6;
    border-top-color: #0070d2;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin: 0 auto 1rem;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

.list {
    list-style: none;
    margin: 0;
    padding: 0;
}

.list-item {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1rem 1.5rem;
    border-bottom: 1px solid #d8dde6;
    position: relative;
}

.list-item:last-child {
    border-bottom: none;
}

.list-item:hover {
    background-color: #f4f6f9;
}

.item-content {
    flex: 1;
}

.item-main {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.25rem;
}

.item-name {
    font-weight: 500;
    color: #333;
}

.item-type {
    font-size: 12px;
    color: #706e6b;
    background-color: #f4f6f9;
    padding: 0.125rem 0.5rem;
    border-radius: 4px;
}

.item-secondary {
    font-size: 13px;
    color: #706e6b;
}

.item-actions {
    display: flex;
    gap: 0.5rem;
}

.btn-icon {
    padding: 0.375rem 0.75rem;
    font-size: 12px;
    background-color: white;
    border: 1px solid #d8dde6;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s ease;
}

.btn-icon:hover {
    background-color: #f4f6f9;
}

.btn-danger:hover {
    background-color: #c23934;
    color: white;
    border-color: #c23934;
}

.badge {
    position: absolute;
    top: 0.5rem;
    right: 0.5rem;
    font-size: 10px;
    padding: 0.125rem 0.375rem;
    border-radius: 4px;
}

.badge-first {
    background-color: #2e844a;
    color: white;
}

.badge-last {
    background-color: #706e6b;
    color: white;
}

.pagination {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 1rem;
    padding: 1rem;
    border-top: 1px solid #d8dde6;
}

.btn-page {
    padding: 0.5rem 1rem;
    font-size: 14px;
    background-color: white;
    border: 1px solid #d8dde6;
    border-radius: 4px;
    cursor: pointer;
}

.btn-page:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.btn-page:hover:not(:disabled) {
    background-color: #f4f6f9;
}

.page-info {
    font-size: 14px;
    color: #706e6b;
}
```
