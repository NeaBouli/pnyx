﻿using System;
using System.Data;
using Common.Data;
using Common.Entities;

namespace Common.Services
{
    /// <summary>
    /// Implementation of the ExcelImporterService
    /// </summary>
    public class ExcelImporterService
    {
        /// <summary>
        /// Occurs when [table imported].
        /// </summary>
        public event EventHandler<NameCountEventArgs> TableImported;

        /// <summary>
        /// Imports the excel file.
        /// </summary>
        /// <param name="fullPathToExcelFile">The full path to excel file.</param>
        /// <exception cref="System.NotImplementedException">Will be thrown if unknown sheet is there</exception>
        public void ImportExcelFile(string fullPathToExcelFile)
        {
            ExcelDataContext.FullPathToXlsFile = fullPathToExcelFile;
            ExcelDataContext excelDataContext = ExcelDataContext.GetInstance();

            foreach (DataTable dataTable in excelDataContext.Sheets)
            {
                switch (dataTable.TableName)
                {
                    case "TransactionTypes":
                        ImportTransactionTypes(dataTable);
                        break;
                    case "Users":
                        ImportUsers(dataTable);
                        break;
                    case "Wallets":
                        ImportWallets(dataTable);
                        break;
                    case "WalletTransactions":
                        ImportWalletTransactions(dataTable);
                        break;
                    case "Issues":
                        ImportIssues(dataTable);
                        break;
                    case "Proposals":
                        ImportProposals(dataTable);
                        break;
                    case "StakedProposals":
                        ImportStakedProposals(dataTable);
                        break;
                    case "Images":
                        ImportImages(dataTable);
                        break;
                    default:
                        throw new NotImplementedException();
                }
            }
        }

        /// <summary>
        /// Imports the staked suggestions.
        /// </summary>
        /// <param name="dataTable">The data table.</param>
        private void ImportStakedProposals(DataTable dataTable)
        {
            StakedProposalService stakedSuggestionService = new StakedProposalService();
            OnTableImported(new NameCountEventArgs("StakedProposals", stakedSuggestionService.Import(dataTable)));
        }

        /// <summary>
        /// Imports the suggestions.
        /// </summary>
        /// <param name="dataTable">The data table.</param>
        private void ImportProposals(DataTable dataTable)
        {
            ProposalService suggestionService = new ProposalService();
            OnTableImported(new NameCountEventArgs("Proposals", suggestionService.Import(dataTable)));
        }

        /// <summary>
        /// Imports the images.
        /// </summary>
        /// <param name="dataTable">The data table.</param>
        private void ImportImages(DataTable dataTable)
        {
            ImageInfoService imageInfoService = new ImageInfoService();
            OnTableImported(new NameCountEventArgs("Images", imageInfoService.Import(dataTable)));
        }

        /// <summary>
        /// Imports the issues.
        /// </summary>
        /// <param name="dataTable">The data table.</param>
        private void ImportIssues(DataTable dataTable)
        {
            IssueService issueService = new IssueService();
            OnTableImported(new NameCountEventArgs("Issues", issueService.Import(dataTable)));
        }

        /// <summary>
        /// Imports the wallet transactions.
        /// </summary>
        /// <param name="dataTable">The data table.</param>
        private void ImportWalletTransactions(DataTable dataTable)
        {
            WalletTransactionService walletTransactionService = new WalletTransactionService();
            OnTableImported(new NameCountEventArgs("WalletTransactions", walletTransactionService.Import(dataTable)));
        }

        /// <summary>
        /// Imports the wallets.
        /// </summary>
        /// <param name="dataTable">The data table.</param>
        private void ImportWallets(DataTable dataTable)
        {
            WalletService walletService = new WalletService();
            OnTableImported(new NameCountEventArgs("Wallets", walletService.Import(dataTable)));
        }

        /// <summary>
        /// Imports the users.
        /// </summary>
        /// <param name="dataTable">The data table.</param>
        private void ImportUsers(DataTable dataTable)
        {
            UserService userService = new UserService();
            OnTableImported(new NameCountEventArgs("Users", userService.Import(dataTable)));
        }

        /// <summary>
        /// Imports the transaction types.
        /// </summary>
        /// <param name="dataTable">The data table.</param>
        private void ImportTransactionTypes(DataTable dataTable)
        {
            TransactionTypeService transactionTypeDbService = new();
            OnTableImported(new NameCountEventArgs("TransactionTypes", transactionTypeDbService.Import(dataTable)));
        }

        /// <summary>
        /// Raises the <see cref="E:TableImported" /> event.
        /// </summary>
        /// <param name="e">The <see cref="NameCountEventArgs"/> instance containing the event data.</param>
        protected virtual void OnTableImported(NameCountEventArgs e)
        {
            TableImported?.Invoke(this, e);
        }
    }
}
