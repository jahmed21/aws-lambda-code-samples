import json
import boto3

# Use paginator from:
# https://boto3.amazonaws.com/v1/documentation/api/latest/guide/paginators.html#filtering-results
# to call recursively on the same API call if next token is returned.

client = boto3.client('lambda')
paginator = client.get_paginator('list_functions')

# Make sure ALL versions are returned for provisioned concurrency
operation_parameters = {'FunctionVersion': 'ALL'}

# Create an empty set to dump all the individual function's data
reserved_concurrency = set()
provisioned_concurrency = set()


def get_provisioned_concurrency(function_name, qualifier):

    response = client.get_provisioned_concurrency_config(
        FunctionName=function_name,
        Qualifier=qualifier
    )

    funct = {
        "Name": function_name,
        "Provisioned Concurrency": response['AllocatedProvisionedConcurrentExecutions']
    }

    funct = json.dumps(funct)
    provisioned_concurrency.add(funct)


def lambda_handler(event, context):
    """ Main function to retrieve reserved concurrency """

    # List all functions
    page_iterator = paginator.paginate()
    for page in page_iterator:
        functions = page['Functions']

        # Check for Reserved Concurrency on a function w/o version(s)
        for function in functions:
            response = client.get_function_concurrency(
                FunctionName=function['FunctionName']
            )

            try:
                funct = {
                    "Name": function['FunctionName'],
                    "Reserved Concurrency": response['ReservedConcurrentExecutions']
                }
                funct = json.dumps(funct)
                reserved_concurrency.add(funct)

            except:
                # Skip since no Reserved Concurrency
                pass

    # Check for provisioned concurrency under alias and/or versions
    page_iterator = paginator.paginate(**operation_parameters)
    for page in page_iterator:
        functions = page['Functions']

        for function in functions:
            if(function['Version'] != '$LATEST'):
                # Try if get_provisioned_concurrency_config SDK call succeeds
                try:
                    # Try for alias
                    try:
                        aliases = []
                        alias = client.list_aliases(
                            FunctionName=function['FunctionName']
                        )

                        for i in alias['Aliases']:
                            aliases.append(i['Name'])

                        for i in aliases:
                            get_provisioned_concurrency(function['FunctionName'], i)
                    except:
                        pass

                    get_provisioned_concurrency(function['FunctionName'], function['Version'])

                except:
                    # ProvisionedConcurrencyConfigNotFoundException error
                    # skip since none set
                    pass

    print("Reserved concurrency:")
    for i in sorted(reserved_concurrency):
        i = json.loads(i)
        print(f"{i['Name']}: {i['Reserved Concurrency']}")

    print("=====================")

    print("Provisioned concurrency:")
    for i in sorted(provisioned_concurrency):
        i = json.loads(i)
        print(f"{i['Name']}: {i['Provisioned Concurrency']}")

    return {
        'statusCode': 200,
        'body': json.dumps('Completed execution')
    }
